import abc
import optparse
import random
import numpy as np
from typing import cast
from scipy import signal
from scipy import fft
from scipy import interpolate
from matplotlib import colormaps
from math import ceil
from pytui import StyledWindow, Plot, Text
from radio import Radio, RtlRadio, PlutoRadio


# returns a matplotlib color map as rgb tuples
def get_colormap(name: str) -> list[tuple[int, int, int]]:
    colors = [colormaps[name](x) for x in range(0, 256)]
    return [(int(r*255), int(g*255), int(b*255)) for (r, g, b, a) in colors]


# returns a gradient between two colors as rgb tuples
def color_gradient(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    n: int
) -> list[tuple[int, int, int]]:
    gradient = [start]
    for t in range(1, n):
        gradient.append(cast(tuple[int, int, int], tuple([
          int(start[j] + (float(t)/(n-1))*(end[j]-start[j]))
          for j in range(3)
        ])))
    return gradient


def get_matrix_colormap() -> list[tuple[int, int, int]]:
    black = (0, 0, 0)
    vampire = (0x0d, 0x02, 0x08)
    dark_green = (0x00, 0x3b, 0x00)
    islamic_green = (0x00, 0x8f, 0x11)
    malachite = (0x00, 0xff, 0x41)
    return (
        color_gradient(black, vampire, 96)
        + color_gradient(vampire, dark_green, 32)
        + color_gradient(dark_green, islamic_green, 64)
        + color_gradient(islamic_green, malachite, 64)
    )


Styles: dict[str, dict] = {
    # colors from
    # https://marketplace.visualstudio.com/items?itemName=enkia.tokyo-night
    'tokyonight': {
        'waterfall-glyph': lambda: '█',
        'colormap': get_colormap('viridis'),
        'header': {'bg': 0x1a1b26, 'fg': 0xa9b1d6},
        # 'plot': {'bg': 0x24283b, 'fg': 0xf7768e},   # red
        'plot': {'bg': 0x24283b, 'fg': 0x7aa2f7},   # blue
        'plot-label': {'bg': 0x24283b, 'fg': 0x565f89}
    },

    # https://matplotlib.org/matplotblog/posts/matplotlib-cyberpunk-style/
    'cyberpunk': {
        'waterfall-glyph': lambda: '█',
        'colormap': get_colormap('viridis'),
        'header': {'bg': 0x2A3459, 'fg': 0x08F7FE},
        # 'plot': {'bg': 0x2A3459, 'fg': 0x08F7FE},
        'plot': {'bg': 0x2A3459, 'fg': 0xFE53BB},
        'plot-label': {'bg': 0x2A3459, 'fg': 0x08F7FE}
    },

    # https://www.schemecolor.com/matrix-code-green.php
    'matrix': {
        'waterfall-glyph': lambda: random.choice(
            'ｦｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ'
        ),
        'colormap': get_matrix_colormap(),
        'header': {'bg': 0x0d0208, 'fg': 0x008f11},
        'plot': {'bg': 0x0d0208, 'fg': 0x00ff41},
        'plot-label': {'bg': 0x0d0208, 'fg': 0x008f11}
    },

    # https://www.nordtheme.com/docs/colors-and-palettes
    'nord': {
        'waterfall-glyph': lambda: '█',
        'colormap': get_colormap('cividis'),
        'header': {'bg': 0xd8dee9, 'fg': 0x81a1c1},
        'plot': {'bg': 0xeceff4, 'fg': 0x2e3440},
        'plot-label': {'bg': 0xd8dee9, 'fg': 0x81a1c1}
    },


}


def format_freq(f: float) -> str:
    if f >= 1e9:
        (f, s) = (f/1e6, 'Ghz')
    else:
        (f, s) = (f/1e3, 'Mhz')

    return f'{(f/1000):.4f}'.rstrip('0').rstrip('.') + ' ' + s


def make_frequency_labels(width: int, start: float, end: float) -> str:
    # *2 to account for flipping at midpoint
    maxWidth = 2*len('|999.9999 Mhz ')
    n = ceil(width/maxWidth)
    # ensure odd number of ticks to get one in the middle
    n = n-1 if n % 2 == 0 else n

    ticks = np.linspace(0, width, n)
    values = np.linspace(start, end, len(ticks))
    labels = ''.ljust(width)

    for i in range(0, n):
        hz = format_freq(values[i])
        if i < n / 2:
            (hz, x) = ('|'+hz, int(ticks[i]))
        else:
            (hz, x) = (hz+'|', int(ticks[i]) - len(hz+'|'))
        labels = labels[:x] + hz + labels[x + len(hz):]

    return labels


def make_db_labels(width: int, height: int, mindb: float, maxdb: float) -> str:
    scale = [' '.ljust(width)]*height
    labels = np.linspace(maxdb, mindb, height//2)
    for i, label in enumerate(labels):
        scale[i*2] = str(round(label)).rjust(width)
    return "\n".join(scale)


def get_psd(
    sample: list[np.complex64],
    window: str = 'hann',
    nperseg: int = None,
    fs: int = None
) -> list[float]:
    if nperseg is None or nperseg == len(sample):
        _, power = signal.periodogram(
            sample,
            window=window,
            return_onesided=False
        )
    else:
        _, power = signal.welch(
            sample,
            window=window,
            return_onesided=False,
            nperseg=nperseg,
            fs=fs
        )
    return fft.fftshift(power)


def to_db(values: list[float]) -> list[float]:
    return list(10.0 * np.log10(values))


def zero_adjust(values: list[float], offset: float) -> list[float]:
    return [x - offset for x in values]


def to_dbfs(values: list[float], offset: float) -> list[float]:
    return zero_adjust(to_db(values), offset)


# fits a list of one size to another by lerping the values
def fit_values(values: list[float], length: int) -> list[float]:
    if len(values) == length:
        return values
    # create function to interpolate from 0-length to values
    x = np.arange(0, len(values))
    f = interpolate.interp1d(np.arange(0, len(values)), values, kind='nearest')
    # linearly subdivide x into length sample
    sx = np.linspace(x[0], x[-1], length)
    # scale sample into new length
    return f(sx)


class Visualizer(abc.ABC):
    def __init__(
        self,
        radio: Radio,
        style: dict = Styles['tokyonight']
    ) -> None:
        self.radio = radio
        self.windows: list[StyledWindow] = []
        self.style = style

    @abc.abstractmethod
    def layout(self, container: StyledWindow) -> None:
        pass

    @abc.abstractmethod
    def update_sample(self, sample: list[np.complex64]) -> None:
        pass

    @abc.abstractmethod
    def update_radio(self, radio: Radio) -> None:
        pass

    def draw(self) -> None:
        for window in self.windows:
            window.draw()


class FFTVisualizer(Visualizer):
    def __init__(
        self,
        radio: Radio,
        mindbfs: int = 0,
        maxdbfs: int = 50,
        nperseg: int = 1024,
        window: str = 'hann',
        zoff: float = -1.0,
        style: dict = Styles['tokyonight']
    ) -> None:
        super().__init__(radio, style)
        self.mindbfs = mindbfs
        self.maxdbfs = maxdbfs
        self.nperseg = nperseg
        self.window = window
        self.zoff = zoff

    def get_dbfs(self, sample: list[np.complex64]) -> list[float]:
        return to_dbfs(get_psd(
            sample,
            window=self.window,
            nperseg=self.nperseg,
            fs=self.radio.rx_bw()
        ), self.zoff)


class Seek(FFTVisualizer):
    def __init__(
        self,
        radio: Radio,
        fstart: float,
        fstop: float,
        mindbfs: int = 0,
        maxdbfs: int = 50,
        nperseg: int = 1024,
        window: str = 'hann',
        zoff: float = -1.0,
        style: dict = Styles['tokyonight']
    ) -> None:
        super().__init__(radio, mindbfs, maxdbfs, nperseg, window, zoff, style)
        self.fstart = fstart
        self.fstop = fstop
        self.signals: dict[int, float] = {}

    def find_signals(
        self,
        sample: list[np.complex64]
    ) -> list[tuple[int, float]]:
        dbfs = self.get_dbfs(sample)
        return [(i, x) for i, x in enumerate(dbfs) if x >= self.mindbfs]

    def have_signal(self, sample: list[np.complex64]) -> bool:
        return len(self.find_signals(sample)) > 0

    def layout(self, container: StyledWindow) -> None:
        dbwidth = max(len(str(self.mindbfs)), len(str(self.maxdbfs)))

        (self.header, body) = container.hsplit(1)
        (self.yaxis, body) = body.vsplit(dbwidth)
        (self.plot, self.xaxis) = body.hsplit(None, 1)

        self.windows = [self.header, self.plot, self.xaxis, self.yaxis]

        self.header.update_style(self.style['header'])
        self.plot.update_style(self.style['plot'])
        self.xaxis.update_style(self.style['plot-label'])
        self.yaxis.update_style(self.style['plot-label'])

        self.update_header()
        self.update_yaxis()
        self.update_xaxis()

    def update_header(self) -> None:
        f = self.radio.rx_freq()
        peak = 'None'
        if self.signals:
            peakf = max(self.signals, key=lambda k: self.signals[k])
            peakdb = round(self.signals[peakf])
            peak = f'{peakf:8} ({peakdb})'

        self.header.update_content(
            f'now:{f:8} | '
            f'peak:{peak}'
        )

    def update_xaxis(self) -> None:
        self.xaxis.update_content(make_frequency_labels(
            self.xaxis.width, self.fstart, self.fstop
        ))

    def update_yaxis(self) -> None:
        self.yaxis.update_content(make_db_labels(
            self.yaxis.width,
            self.yaxis.height-1,  # account for xaxis labels
            self.mindbfs,
            self.maxdbfs
        ))

    def update_plot(self) -> None:
        plot = Plot(
            self.plot.width,
            self.plot.height,
            self.fstart,
            self.mindbfs,
            self.fstop,
            self.maxdbfs
        )

        for freq, dbfs in self.signals.items():
            plot.point(freq, dbfs)

        self.plot.update_content(plot.draw())

    def update_sample(self, sample: list[np.complex64]) -> None:
        signals = self.find_signals(sample)
        update = False

        for foff, dbfs in signals:
            freq = self.radio.rx_freq()+(foff-self.radio.rx_bw()//2)

            if freq not in self.signals or self.signals[freq] < dbfs:
                update = True
                self.signals[freq] = dbfs
                if dbfs > self.maxdbfs:
                    self.maxdbfs = round(dbfs)

        if update:
            self.update_yaxis()
            self.update_plot()

    def update_radio(self, radio: Radio) -> None:
        self.radio = radio
        self.update_header()


class PSD(FFTVisualizer):
    def layout(self, container: StyledWindow) -> None:
        dbwidth = max(len(str(self.mindbfs)), len(str(self.maxdbfs)))
        (self.yaxis, body) = container.vsplit(dbwidth)
        (self.plot, self.xaxis) = body.hsplit(None, 1)

        self.windows = [self.plot, self.xaxis, self.yaxis]

        self.plot.update_style(self.style['plot'])
        self.xaxis.update_style(self.style['plot-label'])
        self.yaxis.update_style(self.style['plot-label'])

        self.update_yaxis()
        self.update_xaxis()

    def update_xaxis(self) -> None:
        f = self.radio.rx_freq()
        r = self.radio.rx_bw()
        self.xaxis.update_content(make_frequency_labels(
            self.xaxis.width, f-r/2, f+r/2
        ))

    def update_yaxis(self) -> None:
        self.yaxis.update_content(make_db_labels(
            self.yaxis.width,
            self.yaxis.height-1,  # account for xaxis labels
            self.mindbfs,
            self.maxdbfs
        ))

    def update_plot(self, values: list[float]) -> None:
        plot = Plot(
            self.plot.width,
            self.plot.height,
            0,
            self.mindbfs,
            len(values),
            self.maxdbfs
        )

        (x1, y1) = (0, values[0])
        for x in range(1, len(values)):
            y = values[x]
            plot.line(x1, y1, x, y)
            (x1, y1) = (x, y)

        self.plot.update_content(plot.draw())

    def update_sample(self, sample: list[np.complex64]) -> None:
        self.update_plot(self.get_dbfs(sample))

    def update_radio(self, radio: Radio) -> None:
        self.radio = radio
        self.update_xaxis()


class Waterfall(FFTVisualizer):
    def layout(self, container: StyledWindow) -> None:
        (self.waterfall, self.xaxis) = container.hsplit(None, 1)
        self.windows = [self.waterfall, self.xaxis]

        self.xaxis.update_style(self.style['plot-label'])
        self.update_xaxis()

    def update_xaxis(self) -> None:
        f = self.radio.rx_freq()
        r = self.radio.rx_bw()
        self.xaxis.update_content(make_frequency_labels(
            self.xaxis.width, f-r/2, f+r/2
        ))

    def update_sample(self, sample: list[np.complex64]) -> None:
        def norm(x: float) -> int:
            x = min(max(x, self.mindbfs), self.maxdbfs)
            return int((x-self.mindbfs)/(self.maxdbfs-self.mindbfs) * 255)

        dbfs = self.get_dbfs(sample)

        # lerp to waterfall width and normalize values to 0-255
        values = [norm(x) for x in fit_values(dbfs, self.waterfall.width)]

        # map to rgb value in style colormap
        colors = [self.style['colormap'][x] for x in values]

        # map to styled glyph
        chars = [
            Text(self.style['waterfall-glyph']()).style({
                'bg': self.style['plot']['bg'],
                'fg': x
            })
            for x in colors
        ]

        self.waterfall.append_line(''.join(chars))

    def update_radio(self, radio: Radio) -> None:
        self.radio = radio
        self.update_xaxis()


class Constellation(Visualizer):
    def __init__(
        self,
        radio: Radio,
        iqrange: int = 1,
        style: dict = Styles['tokyonight']
    ) -> None:
        super().__init__(radio, style)
        self.iqrange = iqrange

    def layout(self, container: StyledWindow) -> None:
        self.plot = container
        self.plot.update_style(self.style['plot'])
        self.windows = [self.plot]

    def update_sample(self, sample: list[np.complex64]) -> None:
        r = self.iqrange
        plot = Plot(self.plot.width, self.plot.height, -r, -r, r, r)
        # axis
        plot.line(-r, 0, r, 0)
        plot.line(0, r, 0, -r)
        # iq points
        for point in zip(np.real(sample), np.imag(sample)):
            plot.point(point[0], point[1])
        self.plot.update_content(plot.draw())

    def update_radio(self, radio: Radio) -> None:
        pass


def parse_frange(radio: Radio, options: optparse.Values) -> tuple[int, int]:
    minf = radio.min_freq()
    maxf = radio.max_freq()

    if options.frange is None:
        return (minf, maxf)
    else:
        (fstart, fstop) = options.frange.split(':')
        fstart = minf if fstart == '' else min(maxf, max(minf, int(fstart)))
        fstop = maxf if fstop == '' else min(maxf, max(minf, int(fstop)))
        if fstart > fstop:
            raise optparse.OptionValueError('start frequency higher than stop')
        options.frange = (fstart, fstop)
    return options.frange


def config_visualizer(
    name: str,
    radio: Radio,
    options: optparse.Values
) -> Visualizer:
    (fftsize, nperseg) = (options.fftsize, options.nperseg)
    # default to non-segmented periodogram for RtlRadio
    dnperseg = fftsize if isinstance(radio, RtlRadio) else fftsize//4
    nperseg = dnperseg if nperseg is None else min(fftsize, nperseg)

    if name == 'psd':
        return PSD(
            radio,
            mindbfs=options.mindbfs,
            maxdbfs=options.maxdbfs,
            nperseg=nperseg,
            window=options.window,
            zoff=-1.0,
            style=Styles[options.style]
        )
    elif name == 'waterfall':
        return Waterfall(
            radio,
            mindbfs=options.mindbfs,
            maxdbfs=options.maxdbfs,
            nperseg=nperseg,
            window=options.window,
            zoff=-1.0,
            style=Styles[options.style]
        )
    elif name == 'seek':
        (fstart, fstop) = parse_frange(radio, options)

        return Seek(
            radio,
            fstart=fstart,
            fstop=fstop,
            mindbfs=options.mindbfs,
            nperseg=nperseg,
            window=options.window,
            zoff=-1.0,
            style=Styles[options.style]
        )
    elif name == 'constellation':
        iqrange = 16384 if isinstance(radio, PlutoRadio) else 1
        return Constellation(radio, iqrange, Styles[options.style])
    else:
        raise optparse.OptionValueError(f'unknown visualizer {name}.')
