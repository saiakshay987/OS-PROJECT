# ml/record_team.py — run once per person, same USB mic you'll use in the demo
import sounddevice as sd, soundfile as sf, os, time
WORDS = ["up","down","left","right","stop","go","yes","no","on","off"]
who = input("your name: ")
for w in WORDS:
    os.makedirs(f"ml/team_data/{w}", exist_ok=True)
    for i in range(30):
        input(f"[{w} {i+1}/30] press Enter, then say '{w}' ")
        x = sd.rec(16000, samplerate=16000, channels=1, dtype="int16"); sd.wait()
        sf.write(f"ml/team_data/{w}/{who}_{i:02d}.wav", x, 16000)
# also record 5 minutes of room noise + people talking normally (→ _silence_ / _unknown_)
