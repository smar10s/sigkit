import signal
from optparse import OptionParser
from pytui import Terminal, StyledWindow, shutdown
from visualizers import Seek
from radio import PlutoRadio


parser = OptionParser('usage: %prog [options]')

parser.add_option('-f', '--frange', type='string', default=None, help=(
    'frequency range expressed as min:max. '
    'defaults to radio range.'
))

parser.add_option('-r', '--rate', type='int', default=int(1e6), help=(
    'sample rate/bandwidth/step size. '
    'default %default hz.'
))

parser.add_option('-l', '--linger', type='int', default=40, help=(
    'number of samples to collect before moving to next frequency. '
    'default %default.'
))

parser.add_option('-p', '--mindbfs', type='int', default=0, help=(
    'record signals above this dbfs threshold. '
    'default %default.'
))

# fft options
parser.add_option('--fftsize', type='int', default=1024, help=(
    'rx buffer and fft size. '
    'default %default.'
))

parser.add_option('--nperseg', type='int', default=None, help=(
    "welch's method segment size. set to fft size to use faster non-segmented "
    'periodogram. '
    'default fftsize/4.'
))

parser.add_option('--window', type='string', default='hann', help=(
    "any scipy windowing function that doesn't require parameters (boxcar, "
    "blackman, hamming, hann, etc). "
    'default %default.'
))

parser.add_option('--gain', type='string', default='fast', help=(
    "rx gain in db, or auto attack style (fast or slow). "
    'default %default'
))


(options, args) = parser.parse_args()

# radio config
radio = PlutoRadio()
radio.update_rx_buffer_size(options.fftsize)
radio.update_rx_bw(options.rate)

if options.gain in ('fast', 'slow'):
    radio.update_rx_auto_gain(options.gain + '_attack')
else:
    radio.update_rx_gain(int(options.gain))

minf = radio.min_freq()
maxf = radio.max_freq()

if options.frange is None:
    options.frange = (minf, maxf)
else:
    (fstart, fstop) = options.frange.split(':')
    fstart = minf if fstart == '' else min(maxf, max(minf, int(fstart)))
    fstop = maxf if fstop == '' else min(maxf, max(minf, int(fstop)))
    options.frange = (fstart, fstop)
(fstart, fstop) = options.frange

# ui config
terminal = Terminal()
terminal.fullscreen()

(fftsize, nperseg) = (options.fftsize, options.nperseg)

seek = Seek(
    radio,
    fstart=fstart,
    fstop=fstop,
    mindbfs=options.mindbfs,
    nperseg=fftsize//4 if nperseg is None else min(fftsize, nperseg),
    window=options.window
)

seek.layout(
    StyledWindow(0, 0, terminal.get_columns(), terminal.get_lines())
)

signal.signal(signal.SIGINT, shutdown)


# seek signal
(step, linger) = (options.rate, options.linger)
while True:
    for f in range(fstart, fstop+step, step):
        radio.update_rx_freq(f)
        seek.update_header()

        for i in range(linger):
            sample = radio.rx()

            if seek.have_signal(sample):
                seek.update_sample(sample)
                break

        seek.draw()
        terminal.flush()
