#!/usr/bin/env python3
import argparse
from file_read_backwards import FileReadBackwards
import logging
from pathlib import Path
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY
from prometheus_client import start_http_server
import signal
import sys
import os


l = logging.getLogger(__name__)
lh = logging.StreamHandler(sys.stdout)
lh.setFormatter(logging.Formatter("[%(levelname)s]: %(message)s"))
l.addHandler(lh)


def removesuffix(string, suffix):
    # Python < 3.9 does not have the str.removesuffix method
    if len(suffix) > 0 and string.endswith(suffix):
        return string[:-len(suffix)]
    return string


def removeprefix(string, prefix):
    # Python < 3.9 does not have the str.removeprefix method
    if len(prefix) > 0 and string.startswith(prefix):
        return string[len(prefix):]
    return string


class FfmpegCollector(object):
  def __init__(self, watch_path):
    self.watch_path = watch_path
    l.info(f"watching {self.watch_path}")

  def collect(self):
    c_frame = CounterMetricFamily('ffmpeg_progress_frame', 'processed frames', labels=['id'])
    c_bytes = CounterMetricFamily('ffmpeg_progress_bytes', 'output bytes', labels=['id'])
    c_us = CounterMetricFamily('ffmpeg_progress_us', 'timestamp of current frame', labels=['id'])
    c_drop = CounterMetricFamily('ffmpeg_progress_dropped', 'dropped frames', labels=['id'])
    c_dup = CounterMetricFamily('ffmpeg_progress_duplicate', 'duplicate frames', labels=['id'])
    g_q = GaugeMetricFamily('ffmpeg_progress_quantizer', 'quantizer', labels=['id', 'output', 'stream'])
    g_speed = GaugeMetricFamily('ffmpeg_progress_speed', 'speed', labels=['id'])

    filenames = os.listdir(self.watch_path)

    for filename in filenames:
      file = Path(self.watch_path) / Path(filename)
      l.debug(f"reading progress on {file}")

      identifier = filename.split('.')[0]

      with FileReadBackwards(file, encoding="utf-8") as frb:
        # the first line indicates if the ffmpeg processing is finished. in that case we ignore the process file
        # to avoid exposing duplicate stale data points until the file has been cleared away
        first_line = frb.readline().strip()
        if first_line == "": # yeah, so sometimes there are just empty lines at the end. fun times.
          first_line = frb.readline().strip()
        if first_line == "progress=end":
          l.debug('progress=end, skipping')
          continue

        while True:
          # read in lines backwards
          line = frb.readline()
          # until we hit another "progress" line, indicating that we have read one progress
          if not line or line.startswith("progress"):
            break
          parts = line.split('=')
          key = parts[0].strip()
          value = parts[1].strip()

          try:
            l.debug(f"key '{key}' value '{value}'")
            if key == 'frame':
              c_frame.add_metric([identifier], float(value))
            if key == 'total_size':
              c_bytes.add_metric([identifier], float(value))
            if key == 'out_time_us':
              c_us.add_metric([identifier], float(value))
            if key == 'drop_frames':
              c_drop.add_metric([identifier], float(value))
            if key == 'dup_frames':
              c_dup.add_metric([identifier], float(value))
            if key.startswith('stream') and key.endswith('q'):
              # example: stream_0_0_q=22.0
              output, stream = filter(None, removeprefix(removesuffix(key, 'q'), 'stream').split('_'))
              g_q.add_metric([identifier, output, stream], float(value))
            if key == 'speed':
              g_speed.add_metric([identifier], float(removesuffix(value, 'x')))

          except ValueError:
            l.debug(f"key '{key}' contained value '{value}' which was not castable to float. ignoring.")

    yield c_frame
    yield c_bytes
    yield c_us
    yield c_drop
    yield c_dup
    yield g_q
    yield g_speed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ffmpeg progress file exporter')
    parser.add_argument('-i', '--watch-path', help='watch for ffmpeg process files in this path', type=str, default='/tmp/ffmpeg')
    parser.add_argument('-p', '--listen-port', help='expose prometheus metrics on this port', type=int, default=2342)
    parser.add_argument('-v', '--verbose', help='increase verbosity level', action='count', default=0)
    args = parser.parse_args()

    # set logging verbosity
    loglevel = max(logging.INFO - (10 * args.verbose), 10)
    l.setLevel(loglevel)

    REGISTRY.register(FfmpegCollector(args.watch_path))
    start_http_server(args.listen_port)
    signal.pause()
