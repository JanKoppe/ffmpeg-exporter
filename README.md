# ffmpeg-exporter

Prometheus exporter that can read ffmpeg progress file and expose metrics from running ffmpeg processes.

## usage

This exporter looks for ffmpeg progress file in a directory. So, the first step is to get your ffmpeg process(es) to write a progress file in a directory, e.g. `/tmp/ffmpeg`.

You can do this by using the `-progress` argument for ffmpeg:

```sh
$ ffmpeg ... -progress /tmp/ffmpeg/myfancytranscodejob.txt
```

In this case the exporter will read the progess file in and label it with the id `myfancytranscodejob`.

You want to start the exporter by pointing it to the watched path, and maybe set a different port to listen on:

```sh
$ ./ffmpeg-exporter.py -i /tmp/ffmpeg -p 1234
```

The watched path needs to exist before starting the exporter. The exporter will not create the path for you.

Don't forget to add the exporter as a scrape target in Prometheus. ffmpeg will by default write progress reports every second, so decreasing the scrape interval will get more data resolution, with the tradeoff being more file read i/o.

Neither ffmpeg nor the ffmpeg-exporter will take care off cleaning up the progress files. You need to do this on your own. One possible solution for batch processing is to take a look at the modified time and delete the raw progress files after the process has finished:
```crontab
* * * * * /usr/bin/find /tmp/ffmpeg/ -mmin +1 -delete
```

## exposed metrics

| metric name                   | type    | description                                                                                     |
| ----------------------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `ffmpeg_progress_frame_total` | Counter | Total amount of processed frames so far                                                         |
| `ffmpeg_progress_bytes_total` | Counter | Total bytes that have been output so far                                                        |
| `ffmpeg_progress_us_total`    | Counter | Timestamp of the last frame                                                                     |
| `ffmpeg_progress_drop_total`  | Counter | Total amount of dropped frames so far                                                           |
| `ffmpeg_progress_dup_total`   | Counter | Total amount of duplicated frames so far                                                        |
| `ffmpeg_progress_quantizer`   | Gauge   | Quantizer value per output and stream, as indicated by additional labels `output` and `stream`. |
| `ffmpeg_progress_speed`       | Gauge   | Current encoding speed, this is calculated as the ratio of output FPS versus input FPS          |

## architecture

Upon each scrape query, the exporter will open every file in the watched directory, and attempt to read the last dataset from the end of the file. It will then parse the metrics values and expose them.

When progress in a file has finished (indicated by a `progress=end` line), the file will be ignored. This avoids exposing the same data point multiple times, even though the ffmpeg process is stopped.
