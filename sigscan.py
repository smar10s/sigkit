import signal
from time import time, sleep
from optparse import OptionParser, OptionGroup, OptionValueError
from pytui import Terminal, StyledWindow, shutdown
from visualizers import configure_visualizer
from radio import PlutoRadio


parser = OptionParser('usage: %prog [options]')

# scanner options
group = OptionGroup(parser, 'Scanner')
parser.add_option_group(group)

group.add_option('-f', '--frequency', type='int', default=int(100e6), help=(
    'centre frequency. '
    'default %default hz'
))

group.add_option('--mindbfs', type='int', default=-50, help=(
    'plot min dbfs. '
    'default %default.'
))

group.add_option('--maxdbfs', type='int', default=40, help=(
    'plot max dbfs. '
    'default %default.'
))

# fft options
group = OptionGroup(parser, 'FFT (if applicable)')
parser.add_option_group(group)

group.add_option('--fftsize', type='int', default=1024, help=(
    'rx buffer and fft size. '
    'default %default.'
))

group.add_option('--nperseg', type='int', default=None, help=(
    "welch's method segment size. "
    'set to fft size to use non-segmented periodogram. '
    'default fftsize/4.'
))

group.add_option('--window', type='string', default='hann', help=(
    "any scipy windowing function that doesn't require parameters (boxcar, "
    'blackman, hamming, hann, etc). '
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
    'default %default.'
))

# ui options
group = OptionGroup(parser, 'Display')
parser.add_option_group(group)

group.add_option(
    '-v', '--visualizers', type='string', default='psd,waterfall', help=(
        'comma-separated list of visualizers. available options are psd and '
        'waterfall. '
        'default %default.'
    )
)

group.add_option('--fps', type='int', default=0, help=(
    'frames (rows) to display per second, 0 to not throttle. '
    'default %default.'
))

group.add_option('--style', type='string', default='tokyonight', help=(
    'visual style. options are tokyonight. '
    'default %default.'
))

(options, args) = parser.parse_args()

# radio config
radio = PlutoRadio()
radio.update_rx_buffer_size(options.fftsize)
radio.update_rx_bw(options.rate)
radio.update_rx_freq(options.frequency)

if options.gain in ('fast', 'slow'):
    radio.update_rx_auto_gain(options.gain + '_attack')
else:
    radio.update_rx_gain(int(options.gain))

# ui config
terminal = Terminal()

container = StyledWindow(0, 0, terminal.get_columns(), terminal.get_lines())

visopt = options.visualizers.split(',')
visualizers = [configure_visualizer(x, radio, options) for x in visopt]

if len(visualizers) == 1:
    visualizers[0].layout(container)
elif len(visualizers) == 2:
    (top, bottom) = container.hsplit(0.35)
    visualizers[0].layout(top)
    visualizers[1].layout(bottom)
elif len(visualizers) == 3:
    (top, middle, bottom) = container.hsplit(0.33, 0.33)
    visualizers[0].layout(top)
    visualizers[1].layout(middle)
    visualizers[2].layout(bottom)
else:
    raise OptionValueError(f'invalid layout: {options.visualizers}')

signal.signal(signal.SIGINT, lambda signal, frame: shutdown())

try:
    terminal.fullscreen()

    while True:
        start = time()
        sample = radio.rx()
        for v in visualizers:
            v.update_sample(sample)
            v.draw()
        terminal.flush()
        delta = time() - start
        if options.fps != 0:
            sleep(max(0, (1/options.fps) - delta))
finally:
    shutdown()
