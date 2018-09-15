import neopixel
import time
import sys
import json
import datetime
import logging
import logging.handlers
from noaatides import predictions
from noaatides import task

# LED strip configuration:
LED_COUNT = 3  # Number of LED pixels.
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal (try 10)
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_STRIP = neopixel.ws.WS2811_STRIP_GRB  # Strip type and colour ordering

COLOR_OFF = neopixel.Color(0, 0, 0)
COLOR_RED = neopixel.Color(255, 0, 0)
COLOR_YELLOW = neopixel.Color(255, 255, 0)
COLOR_GREEN = neopixel.Color(0, 255, 0)

logger = logging.getLogger(__name__)


def init_logger(file_name):
    formatter = logging.Formatter('[%(asctime)s] <%(threadName)s> %(levelname)s - %(message)s')

    handler = logging.handlers.RotatingFileHandler(file_name, maxBytes=100000, backupCount=3)
    handler.setFormatter(formatter)

    log = logging.getLogger('')
    log.setLevel(logging.INFO)
    log.addHandler(handler)


def render(strip, red_led, yellow_led, green_led):
    strip.setPixelColor(0, COLOR_RED if red_led else COLOR_OFF)
    strip.setPixelColor(1, COLOR_YELLOW if yellow_led else COLOR_OFF)
    strip.setPixelColor(2, COLOR_GREEN if green_led else COLOR_OFF)
    strip.show()


def main():
    file_name = sys.argv[1] if len(sys.argv) == 2 else 'config.json'

    with open(file_name, 'rb') as config_file:
        config = json.load(config_file)

    tide_station = config['tide_station']
    tide_time_offset_low = config['tide_time_offset']['low']
    tide_time_offset_high = config['tide_time_offset']['high']
    tide_level_offset_low = config['tide_level_offset']['low']
    tide_level_offset_high = config['tide_level_offset']['high']
    tide_request_window_back = config['tide_request_window']['back']
    tide_request_window_forward = config['tide_request_window']['forward']
    tide_renew_threshold = config['tide_renew_threshold']

    yellow_threshold = config['water_level_thresholds']['yellow']
    green_threshold = config['water_level_thresholds']['green']
    water_level_minutes = datetime.timedelta(minutes=config['water_level_minutes'])

    init_logger(config['log_file_name'])

    strip = neopixel.Adafruit_NeoPixel(
        LED_COUNT,
        config['led_pin'],
        LED_FREQ_HZ,
        LED_DMA,
        LED_INVERT,
        config['led_brightness'],
        LED_CHANNEL,
        LED_STRIP)

    strip.begin()

    time_offset = predictions.AdditiveOffset(
        datetime.timedelta(minutes=tide_time_offset_low),
        datetime.timedelta(minutes=tide_time_offset_high))
    level_offset = predictions.MultiplicativeOffset(
        tide_level_offset_low,
        tide_level_offset_high)
    tide_offset = predictions.TideOffset(time_offset, level_offset)
    query_range = (
        datetime.timedelta(days=tide_request_window_back),
        datetime.timedelta(days=tide_request_window_forward))
    renew_threshold = datetime.timedelta(days=tide_renew_threshold)

    tt = task.TideTask(tide_station, tide_offset, query_range, renew_threshold)
    tt.start()

    while True:
        now = datetime.datetime.utcnow()
        later = now + water_level_minutes
        tide_now = tt.await_tide(now)
        tide_later = tt.await_tide(later)
        logger.info('tide now: {}'.format(tide_now))
        logger.info('tide later: {}'.format(tide_later))
        if tide_now.level >= green_threshold and tide_later.level >= green_threshold:
            render(strip, False, False, True)
        elif tide_now.level >= yellow_threshold and tide_later.level >= yellow_threshold:
            render(strip, False, True, False)
        else:
            render(strip, True, False, False)
        time.sleep(60)


if __name__ == '__main__':
    main()
