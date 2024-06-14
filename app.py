import os
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from openai import OpenAI
from openai.types.beta import Assistant
import pyaudio

OpenaiApiKey = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OpenaiApiKey)

my_assistant = client.beta.assistants.retrieve("asst_g95sff3V5W7glfCKBAmEvZFm")

app = Flask(__name__)
CORS(app)

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000
CHUNK = 1024
audio1 = pyaudio.PyAudio()

def genHeader(sampleRate, bitsPerSample, channels):
    datasize = 2000*10**6
    o = bytes("RIFF", 'ascii')
    o += (datasize + 36).to_bytes(4, 'little')
    o += bytes("WAVE", 'ascii')
    o += bytes("fmt ", 'ascii')
    o += (16).to_bytes(4, 'little')
    o += (1).to_bytes(2, 'little')
    o += (channels).to_bytes(2, 'little')
    o += (sampleRate).to_bytes(4, 'little')
    o += (sampleRate * channels * bitsPerSample // 8).to_bytes(4, 'little')
    o += (channels * bitsPerSample // 8).to_bytes(2, 'little')
    o += (bitsPerSample).to_bytes(2, 'little')
    o += bytes("data", 'ascii')
    o += (datasize).to_bytes(4, 'little')
    return o

@app.route("/GenerateResponse/<prompt>", methods=['GET'])
def generate_response(prompt):
    try:
        my_thread = client.beta.threads.create()

        my_message = client.beta.threads.messages.create(
            thread_id=my_thread.id,
            role='user',
            content=prompt
        )

        my_run = client.beta.threads.runs.create(
            thread_id=my_thread.id,
            assistant_id=my_assistant.id
        )
        print(f"This is the run object: {my_run}")

        while my_run.status in ["queued", "in_progress"]:
            keep_retrieving_run = client.beta.threads.runs.retrieve(
                thread_id=my_thread.id,
                run_id=my_run.id
            )
            print(f"Run status: {keep_retrieving_run.status}")

            if keep_retrieving_run.status not in ["queued", "in_progress"]:
                break

        if keep_retrieving_run.status == "completed":
            all_messages = client.beta.threads.messages.list(
                thread_id=my_thread.id
            )

            print("---------------------------------------------------\n")
            print(f"User: {my_message.content[0].text.value}")
            print(f"Bob: {all_messages.data[0].content[0].text.value}")
            response = all_messages.data[0].content[0].text.value
            resp = response.strip()
            return jsonify({"response": resp})

        return jsonify({"error": "Run not completed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/welcome", methods=["GET"])
def welcome():
    stream_response("Welcome")

@app.route("/game_over", methods=["GET"])
def game_over():
    stream_response("game over")

@app.route("/StreamResponse/<prompt>", methods=["GET"])
def stream_response(prompt):
    response_json = generate_response(prompt).json
    response_text = response_json['response']

    def sound():
        sampleRate = 24000
        bitsPerSample = 16
        channels = 1
        wav_header = genHeader(sampleRate, bitsPerSample, channels)

        stream = audio1.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)

        print("streaming audio...")

        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="onyx",
            input=response_text,
            response_format='pcm'
        ) as response:
            first_run = True
            for chunk in response.iter_bytes(1024):
                if first_run:
                    data = wav_header + chunk
                    first_run = False
                else:
                    data = chunk
                yield data
    return Response(sound(), mimetype='audio/x-wav;codec=pcm')


if __name__ == "__main__":
    app.run(debug=True, threded=True)
