"""Check decoded deliverables, not only the editable timeline."""
import json
import subprocess
import sys
from pathlib import Path


def run(*args):
    return subprocess.check_output(args)


def frame(video, at, crop):
    return run('ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(video),
               '-vf', 'crop=' + crop + ',format=gray', '-frames:v', '1',
               '-f', 'rawvideo', '-')


def verify(video):
    probe = json.loads(run('ffprobe', '-v', 'error', '-show_format', '-show_streams',
                           '-of', 'json', str(video)))
    stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    assert (stream['width'], stream['height']) == (1920, 1080)
    assert stream['r_frame_rate'] == '30/1'
    assert abs(float(probe['format']['duration']) - 75) < .1
    assert any(s['codec_type'] == 'audio' for s in probe['streams'])
    changes = {}
    for name, a, b, crop in [
        ('map_flow', 4, 4.5, '220:260:970:570'),
        ('scrolling_ticker', 4, 4.5, '1200:26:300:1046'),
        ('switch_paths', 16, 16.5, '230:220:550:605'),
        ('port_recovery', 25, 28, '130:50:365:563'),
        ('service_recovery', 50.9, 54, '400:180:130:380'),
    ]:
        first, second = frame(video, a, crop), frame(video, b, crop)
        assert len(first) == len(second) > 0
        changed = sum(abs(x-y) > 12 for x, y in zip(first, second))
        assert changed > 12, (video, name, changed)
        changes[name] = changed
    return {'file': video.name, 'duration': 75, 'resolution': '1920x1080',
            'fps': 30, 'encoder': stream.get('tags', {}).get('encoder'),
            'changed_pixels': changes}


if __name__ == '__main__':
    assert len(sys.argv) > 1, 'Pass the final MP4 paths'
    print(json.dumps([verify(Path(p)) for p in sys.argv[1:]], indent=2))
