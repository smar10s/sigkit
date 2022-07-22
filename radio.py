import abc
import optparse
import numpy as np

# https://wiki.analog.com/university/tools/pluto/users/customizing#updating_to_the_ad9364
PLUTO_FREQ_RANGE = (int(70e6), int(6e9))
PLUTO_BW_RANGE = (int(521e3), int(56e6))

# https://www.rtl-sdr.com/about-rtl-sdr/
# rafael micro
RTLSDR_FREQ_RANGE = (int(24e6), int(1.766e9))
RTLSDR_BW_RANGE = (int(1e6), int(3.2e6))


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
        return PLUTO_FREQ_RANGE[0]

    def max_freq(self) -> int:
        return PLUTO_FREQ_RANGE[1]

    def min_bw(self) -> int:
        return PLUTO_BW_RANGE[0]

    def max_bw(self) -> int:
        return PLUTO_BW_RANGE[1]

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


class RtlRadio(Radio):
    def __init__(self) -> None:
        from rtlsdr import RtlSdr

        self.sdr = RtlSdr()
        self._rx_freq = self.sdr.center_freq
        self._rx_bw = self.sdr.sample_rate
        self._rx_buffer_size = 1024  # some reasonable default

    def min_freq(self) -> int:
        return RTLSDR_FREQ_RANGE[0]

    def max_freq(self) -> int:
        return RTLSDR_FREQ_RANGE[1]

    def min_bw(self) -> int:
        return RTLSDR_BW_RANGE[0]

    def max_bw(self) -> int:
        return RTLSDR_BW_RANGE[1]

    def rx_freq(self) -> int:
        return self._rx_freq

    def update_rx_freq(self, f: int) -> None:
        f = self.clamp(f, self.min_freq(), self.max_freq())
        self.sdr.center_freq = f
        self._rx_freq = f

    def rx_bw(self) -> int:
        return self._rx_bw

    def update_rx_bw(self, fs: int) -> None:
        fs = self.clamp(fs, self.min_bw(), self.max_bw())
        self.sdr.sample_rate = fs
        self._rx_bw = fs

    def update_rx_buffer_size(self, s: int) -> None:
        self._rx_buffer_size = s

    def update_rx_auto_gain(self, attack_type: str) -> None:
        self.sdr.gain = 'auto'

    def update_rx_gain(self, gain: int) -> None:
        self.sdr.gain = gain

    def rx(self) -> list[np.complex64]:
        return self.sdr.read_samples(self._rx_buffer_size)

    def update_tx_freq(self, f: int) -> None:
        raise NotImplementedError()

    def update_tx_bw(self, fs: int) -> None:
        raise NotImplementedError()

    def update_tx_gain(self, gain: int) -> None:
        raise NotImplementedError()


def config_radio(options: optparse.Values) -> Radio:
    radio: Radio

    if options.radio == 'pluto':
        radio = PlutoRadio()
    elif options.radio == 'rtlsdr':
        radio = RtlRadio()
    elif options.radio == 'auto':
        try:
            radio = PlutoRadio()
        except Exception:
            try:
                radio = RtlRadio()
            except Exception:
                raise optparse.OptionValueError('no radio found')
    else:
        raise optparse.OptionValueError(f'unknown radio {options.radio}.')

    if isinstance(radio, PlutoRadio) and options.gain in ('fast', 'slow'):
        radio.update_rx_auto_gain(options.gain + '_attack')
    if isinstance(radio, PlutoRadio) and options.gain == 'auto':
        radio.update_rx_auto_gain('fast_attack')
    elif isinstance(radio, RtlRadio) and options.gain == 'auto':
        radio.update_rx_auto_gain(options.gain)
    else:
        radio.update_rx_gain(int(options.gain))

    radio.update_rx_buffer_size(options.fftsize)
    radio.update_rx_bw(options.rate)

    return radio
