import signal
from optparse import OptionParser, OptionGroup, OptionValueError
from pytui import Terminal, StyledWindow, shutdown
from visualizers import Seek, Styles
from radio import PlutoRadio


parser = OptionParser('usage: %prog [options]')

parser.add_option('-f', '--frange', type='string', default=None, help=(
    'frequency range expressed as min:max. '
    'defaults to radio range.'
))

parser.add_option('-l', '--linger', type='int', default=20, help=(
    'number of samples to collect before moving to next frequency. '
    'default %default.'
))

parser.add_option('-p', '--mindbfs', type='int', default=0, help=(
    'record signals above this dbfs threshold. '
    'default %default.'
))

# fft options
group = OptionGroup(parser, 'FFT')
parser.add_option_group(group)

group.add_option('--fftsize', type='int', default=1024, help=(
    'rx buffer and fft size. '
    'default %default.'
))

group.add_option('--nperseg', type='int', default=None, help=(
    "welch's method segment size. set to fft size to use faster non-segmented "
    'periodogram. '
    'default fftsize/4.'
))

group.add_option('--window', type='string', default='hann', help=(
    "any scipy windowing function that doesn't require parameters (boxcar, "
    "blackman, hamming, hann, etc). "
    'default %default.'
))

# radio options
group = OptionGroup(parser, 'Radio')
parser.add_option_group(group)

group.add_option('-r', '--rate', type='int', default=int(1e6), help=(
    'iq sample rate/bandwidth/step size. '
    'default %default hz.'
))

group.add_option('--gain', type='string', default='fast', help=(
    "rx gain in db, or auto attack style (fast or slow). "
    'default %default'
))

# ui options
group = OptionGroup(parser, 'Display')
parser.add_option_group(group)

group.add_option('--style', type='string', default='tokyonight', help=(
    'visual style. options are tokyonight. '
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

# ui config
terminal = Terminal()

minf = radio.min_freq()
maxf = radio.max_freq()

if options.frange is None:
    options.frange = (minf, maxf)
else:
    (fstart, fstop) = options.frange.split(':')
    fstart = minf if fstart == '' else min(maxf, max(minf, int(fstart)))
    fstop = maxf if fstop == '' else min(maxf, max(minf, int(fstop)))
    if fstart > fstop:
        raise OptionValueError('start frequency must be lower than stop')
    options.frange = (fstart, fstop)
(fstart, fstop) = options.frange

(fftsize, nperseg) = (options.fftsize, options.nperseg)

seek = Seek(
    radio,
    fstart=fstart,
    fstop=fstop,
    mindbfs=options.mindbfs,
    nperseg=fftsize//4 if nperseg is None else min(fftsize, nperseg),
    window=options.window,
    zoff=-1.0,
    style=Styles[options.style]
)

seek.layout(StyledWindow(0, 0, terminal.get_columns(), terminal.get_lines()))

signal.signal(signal.SIGINT, lambda signal, frame: shutdown())

(step, linger) = (options.rate, options.linger)

try:
    terminal.fullscreen()

    # seek
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
finally:
    shutdown()
