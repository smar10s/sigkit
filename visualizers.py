import abc
import numpy as np
from scipy import signal
from scipy import fft
from math import ceil
from pytui import StyledWindow, Plot
from radio import Radio


Styles: dict[str, dict[str, dict[str, int]]] = {
    # colors from
    # https://marketplace.visualstudio.com/items?itemName=enkia.tokyo-night
    'tokyonight': {
        'header': {'bg': 0x1a1b26, 'fg': 0xa9b1d6},
        # 'plot': {'bg': 0x24283b, 'fg': 0xf7768e},   # red
        'plot': {'bg': 0x24283b, 'fg': 0x7aa2f7},   # blue
        'plot-label': {'bg': 0x24283b, 'fg': 0x565f89}
    }
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


def zero_adjust(values: list[float], offset: float = 1.0) -> list[float]:
    return [x - offset for x in values]


def to_dbfs(values: list[float], offset: float = 1.0) -> list[float]:
    return zero_adjust(to_db(values), offset)


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

    def draw(self) -> None:
        for window in self.windows:
            window.draw()


class Seek(Visualizer):
    def __init__(
        self,
        radio: Radio,
        fstart: float,
        fstop: float,
        mindbfs: int = 0,
        maxdbfs: int = 50,
        nperseg: int = 1024,
        window: str = 'hann',
        style: dict = Styles['tokyonight']
    ) -> None:
        super().__init__(radio, style)
        self.fstart = fstart
        self.fstop = fstop
        self.mindbfs = mindbfs
        self.maxdbfs = maxdbfs
        self.nperseg = nperseg
        self.window = window
        self.signals: dict[int, float] = {}

    def find_signals(
        self,
        sample: list[np.complex64]
    ) -> list[tuple[int, float]]:
        dbfs = to_dbfs(get_psd(
            sample,
            window=self.window,
            nperseg=self.nperseg,
            fs=self.radio.rx_bw()
        ))
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
            self.xaxis.width,
            self.fstart,
            self.fstop
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
