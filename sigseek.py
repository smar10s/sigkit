import signal
from optparse import OptionParser, OptionGroup
from pytui import Terminal, StyledWindow, shutdown
from visualizers import Seek, config_visualizer
from radio import config_radio


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
    "welch's method segment size. "
    'set to fft size to use non-segmented periodogram. '
    'default fftsize/4 for pluto, fftsize for rtl.'
))

group.add_option('--window', type='string', default='hann', help=(
    "any scipy windowing function that doesn't require parameters (boxcar, "
    "blackman, hamming, hann, etc). "
    'default %default.'
))

# radio options
group = OptionGroup(parser, 'Radio')
parser.add_option_group(group)

group.add_option('--radio', type='string', default='auto', help=(
    'radio to use. options are "pluto", "rtlsdr" or "auto". auto will select '
    'pluto or rtlsdr depending on which is available. '
    'default %default.'
))

group.add_option('-r', '--rate', type='int', default=int(1e6), help=(
    'iq sample rate/bandwidth/step size. '
    'default %default hz.'
))

group.add_option('--gain', type='string', default='auto', help=(
    'rx gain in db, or auto attack style ("fast"/"auto" or "slow" for pluto, '
    '"auto" for rtlsdr). '
    'default %default.'
))

# ui options
group = OptionGroup(parser, 'Display')
parser.add_option_group(group)

group.add_option('--style', type='string', default='tokyonight', help=(
    'visual style. options are tokyonight, cyberpunk, matrix. '
    'default %default'
))

(options, args) = parser.parse_args()

# radio config
radio = config_radio(options)

# ui config
terminal = Terminal()

seek = config_visualizer('seek', radio, options)
if not isinstance(seek, Seek):
    raise Exception('expected instance of Seek')

seek.layout(StyledWindow(0, 0, terminal.get_columns(), terminal.get_lines()))

signal.signal(signal.SIGINT, lambda signal, frame: shutdown())

# seek
(step, linger) = (options.rate, options.linger)

try:
    terminal.fullscreen()

    # seek
    while True:
        for f in range(int(seek.fstart), int(seek.fstop)+step, step):
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
