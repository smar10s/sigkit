import abc
import numpy as np


class Radio(abc.ABC):
    def clamp(self, v, a, b) -> int:
        return min(max(v, a), b)

    @abc.abstractmethod
    def min_freq(self) -> int:
        pass

    @abc.abstractmethod
    def max_freq(self) -> int:
        pass

    @abc.abstractmethod
    def min_bw(self) -> int:
        pass

    @abc.abstractmethod
    def max_bw(self) -> int:
        pass

    @abc.abstractmethod
    def rx_freq(self) -> int:
        pass

    @abc.abstractmethod
    def update_rx_freq(self, f: int) -> None:
        pass

    @abc.abstractmethod
    def rx_bw(self) -> int:
        pass

    @abc.abstractmethod
    def update_rx_bw(self, fs: int) -> None:
        pass

    @abc.abstractmethod
    def update_rx_buffer_size(self, s: int) -> None:
        pass

    @abc.abstractmethod
    def update_rx_auto_gain(self, attack_type: str) -> None:
        pass

    @abc.abstractmethod
    def update_rx_gain(self, gain: int) -> None:
        pass

    @abc.abstractmethod
    def rx(self) -> list[np.complex64]:
        pass

    @abc.abstractmethod
    def update_tx_freq(self, f: int) -> None:
        pass

    @abc.abstractmethod
    def update_tx_bw(self, fs: int) -> None:
        pass

    @abc.abstractmethod
    def update_tx_gain(self, gain: int) -> None:
        pass


class PlutoRadio(Radio):
    def __init__(self) -> None:
        import adi
        self.sdr = adi.Pluto()
        # cache settings to avoid i/o reads later
        self._rx_freq = self.sdr.rx_lo
        self._rx_bw = self.sdr.rx_rf_bandwidth

    def min_freq(self) -> int:
        return int(70e6)

    def max_freq(self) -> int:
        return int(6e9)

    def min_bw(self) -> int:
        return int(521e3)

    def max_bw(self) -> int:
        return int(56e6)

    def update_rx_freq(self, f: int) -> None:
        f = self.clamp(f, self.min_freq(), self.max_freq())
        self.sdr.rx_lo = f
        self._rx_freq = f

    def rx_freq(self) -> int:
        return self._rx_freq

    def update_rx_bw(self, fs: int) -> None:
        fs = self.clamp(fs, self.min_bw(), self.max_bw())
        # iq sampling, assume sample rate = bandwidth
        self.sdr.rx_rf_bandwidth = fs
        self.sdr.sample_rate = fs
        self._rx_bw = fs

    def rx_bw(self) -> int:
        return self._rx_bw

    def update_rx_buffer_size(self, s: int) -> None:
        self.sdr.rx_buffer_size = s

    def update_rx_auto_gain(self, attack_type: str) -> None:
        self.sdr.gain_control_mode_chan0 = attack_type

    def update_rx_gain(self, gain: int) -> None:
        self.sdr.gain_control_mode_chan0 == 'manual'
        self.sdr.rx_hardwaregain_chan0 = gain

    def rx(self) -> list[np.complex64]:
        return self.sdr.rx()

    def update_tx_freq(self, f: int) -> None:
        self.sdr.tx_lo = f

    def update_tx_bw(self, fs: int) -> None:
        self.sdr.tx_rf_bandwidth = fs

    def update_tx_gain(self, gain: int) -> None:
        self.sdr.tx_hardwaregain_chan0 = gain


# --- work in progress ---

# class RtlRadio():
#     def __init__(self) -> None:
#       import ...
