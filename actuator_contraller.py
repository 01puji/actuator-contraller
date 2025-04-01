# actuator-contraller
import os
import sys
import wave
import time
import serial
import pyaudio
import openai
from openai import OpenAI
import tempfile
import atexit
import threading
import re

from whisper_motor_control import play_audio

# 초기화
SERIAL_PORT = 'COM4'
BAUD_RATE = 115200
OPENAI_API_KEY = ' '
TEMP_DIR = tempfile.gettempdir()

# 전역 변수
is_recording = False
audio_frames = []
recording_thread = None
client = OpenAI(api_key=OPENAI_API_KEY)

try:
    # 아두아노 포트 연결
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"{SERIAL_PORT} 포트를 연결했습니다.")
except serial.SerialException as e:
    print(f"{SERIAL_PORT} 포트를 연결을 못합니다.: {e}")
    sys.exit(1)  

# 오디오 변수
FORMAT = pyaudio.paInt24
CHANNELS = 1
RATE = 48000
CHUNK = 1024
audio = pyaudio.PyAudio()

# 처리 함수
def cleanup():
    for f in os.listdir(TEMP_DIR):
        if f.endswith('.wav'):
            os.remove(os.path.join(TEMP_DIR, f))
    if 'arduino' in globals():
        arduino.close()
    audio.terminate()

atexit.register(cleanup)

# 녹음 콜백 함수
def record_callback(in_data, frame_count, time_info, status):
    if is_recording:
        audio_frames.append(in_data)
    return (in_data, pyaudio.paContinue)

# 녹음 처리
def start_recording():
    global is_recording, recording_thread, audio_frames
    if is_recording:
        return

    is_recording = True
    audio_frames = []
    print("\r녹음 시작합니다.", end="", flush=True)
    recording_thread = threading.Thread(target=record_audio)
    recording_thread.start()

def stop_recording():
    global is_recording, recording_thread
    if not is_recording:
        return

    is_recording = False
    print("\r녹음 종료했습니다. 처리 중입니다.", end="", flush=True)

    if recording_thread:
        recording_thread.join()

    timestamp = str(int(time.time()))
    input_wav = os.path.join(TEMP_DIR, f"input_{timestamp}.wav")

    with wave.open(input_wav, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(audio_frames))

    print(f"\r녹음 파일을 {input_wav}에 저장했습니다. 처리 중입니다.", end="", flush=True)
    process_audio(input_wav)

    # 모터 회전 시간
    time.sleep(5)

# 녹음 실행
def record_audio():
    # print("녹음 시작")
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK,
                        stream_callback=record_callback)
    stream.start_stream()
    while is_recording:
        time.sleep(0.1)
    stream.stop_stream()
    stream.close()

# 음성 인식
def speech_to_text(audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ko"
        )
    return transcript.text.lower()

# 명령 처리
def process_audio(audio_path):
    text = speech_to_text(audio_path)
    if not text:
        print("각도 인식 못합니다. 다시시도 하십시오.")
        return

    print(f"인식된 텍스트：{text}")

    if "왼쪽으로" in text or "좌회전" in text:
        encoder_count = re.search(r"(\d+)도", text)
        if encoder_count:
            angle = int(encoder_count.group(1))
            command = f"2{angle:03d}"
        else:
            print("각도 인식 못합니다. 다시시도 하십시오.")
            return

    elif "오른쪽으로" in text or "우회전" in text:
        encoder_count = re.search(r"(\d+)도", text)
        if encoder_count:
            angle = int(encoder_count.group(1))
            command = f"1{angle:03d}"
        else:
            print("각도 인식 못합니다. 다시시도 하십시오.")
            return

    send_command(command)
    if angle is not None:
        print(f"{angle}도를 회전했습니다.")

# Arduino로 전송
def send_command(command):
    if 'arduino' in globals() and arduino.is_open:
        arduino.write(command.encode())
        print(f"명령을 전송했습니다.: {command}")
    else:
        print("포트가 열리지 않아 명령을 보낼 수 없습니다.")

def main():
    while True: 
        print("프로그램 시작했습니다.")
        start_recording()
        time.sleep(3)  # 녹음시간
        stop_recording()
        print("녹음과 처리가 완료되었습니다. 다음 명령을 기다리고 있습니다.")

if __name__ == "__main__":
    main()
