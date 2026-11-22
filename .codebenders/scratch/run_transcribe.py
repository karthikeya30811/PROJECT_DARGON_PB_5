import sys
sys.path.insert(0, '.')
from engine.stt import transcribe
lang = sys.argv[1]
path = sys.argv[2]
print(repr(transcribe(open(path, 'rb').read(), lang)))
