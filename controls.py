import optparse
import abc
from typing import Callable
from pytui import StyledWindow
from visualizers import config_visualizer, Visualizer
from radio import Radio


class Controls():
    def __init__(
        self,
        radio: Radio,
        visualizers: list[Visualizer],
        options: optparse.Values,
        container: StyledWindow
    ) -> None:
        self.radio = radio
        self.visualizers = visualizers
        self.showing = 'default'
        self.selected_visualizers = self.visualizers.copy()

    @abc.abstractmethod
    def keymap(self) -> dict[str, Callable]:
        pass

    def update_visualizers(self) -> None:
        for v in self.visualizers:
            v.update_radio(self.radio)

    def onkey(self, key: str) -> None:
        keymap = self.keymap()
        if key in keymap:
            keymap[key]()


class ScanControls(Controls):
    def __init__(
        self,
        radio: Radio,
        visualizers: list[Visualizer],
        options: optparse.Values,
        container: StyledWindow
    ) -> None:
        super().__init__(radio, visualizers, options, container)
        # create fullscreen versions of some visualizers for toggling
        self.const = config_visualizer('constellation', radio, options)
        self.const.layout(container)
        self.psd = config_visualizer('psd', radio, options)
        self.psd.layout(container)
        self.waterfall = config_visualizer('waterfall', radio, options)
        self.waterfall.layout(container)

    def keymap(self) -> dict[str, Callable]:
        return {
            '[': lambda: self.update_rx_freq(-1000),
            'a': lambda: self.update_rx_freq(-100000),
            'A': lambda: self.update_rx_freq(-10000000),
            ']': lambda: self.update_rx_freq(1000),
            'd': lambda: self.update_rx_freq(100000),
            'D': lambda: self.update_rx_freq(10000000),
            'w': lambda: self.update_rx_bw(-100000),
            'W': lambda: self.update_rx_bw(-10000000),
            's': lambda: self.update_rx_bw(100000),
            'S': lambda: self.update_rx_bw(10000000),
            'c': lambda: self.toggle_visualizer('constellation', self.const),
            'f': lambda: self.toggle_visualizer('waterfall', self.waterfall),
            'p': lambda: self.toggle_visualizer('psd', self.psd)
            # TODO -/+ for gain
        }

    def update_rx_freq(self, d: int) -> None:
        self.radio.update_rx_freq(self.radio.rx_freq() + d)
        self.update_visualizers()

    def update_rx_bw(self, d: int) -> None:
        self.radio.update_rx_bw(self.radio.rx_bw() + d)
        self.update_visualizers()

    def toggle_visualizer(self, name: str, visualizer: Visualizer) -> None:
        self.visualizers.clear()
        if self.showing == name:
            self.showing = 'default'
            self.visualizers.extend(self.selected_visualizers)
        else:
            self.showing = name
            self.visualizers.append(visualizer)
