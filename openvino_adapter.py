"""OpenVINO GenAI capability probe and isolated NPU-only benchmark."""
import argparse
import json
import math
from pathlib import Path
import statistics

PROMPT = "Explain how a laptop can run an AI model locally in three sentences."
REPETITIONS = 3
MAX_NEW_TOKENS = 32


def probe():
    try:
        import openvino as ov
        devices = list(ov.Core().available_devices)
        npus = [device for device in devices if device.split('.')[0] == 'NPU']
        if not npus:
            return {'status': 'unavailable', 'devices': devices,
                    'message': 'OpenVINO cannot see an NPU. Check the Intel AI Boost driver.'}
        import openvino_genai as genai
        return {'status': 'available', 'devices': devices, 'npu_devices': npus,
                'openvino_version': ov.__version__, 'genai_version': genai.__version__,
                'message': 'OpenVINO detected an NPU. A compatible model can now be tested.'}
    except Exception as error:
        return {'status': 'unavailable', 'devices': [], 'message': str(error)}


def model_folder(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('Choose the full path to a local OpenVINO model folder.')
    path = path.resolve()
    files = ('openvino_model.xml', 'openvino_model.bin', 'openvino_tokenizer.xml',
             'openvino_tokenizer.bin', 'openvino_detokenizer.xml', 'openvino_detokenizer.bin')
    if not all((path / name).is_file() for name in files):
        raise ValueError('Choose an exported OpenVINO text model with XML/BIN model, tokenizer and detokenizer files.')
    return path


def measure(path):
    capability = probe()
    if capability['status'] != 'available':
        raise RuntimeError(capability['message'])
    import openvino_genai as genai

    pipe = genai.LLMPipeline(str(path), 'NPU')
    config = genai.GenerationConfig()
    config.max_new_tokens = MAX_NEW_TOKENS
    config.do_sample = False
    config.apply_chat_template = False
    pipe.generate([PROMPT], config)
    samples = []
    for _ in range(REPETITIONS):
        metrics = pipe.generate([PROMPT], config).perf_metrics
        tokens = metrics.get_num_generated_tokens()
        throughput = metrics.get_throughput().mean
        ttft = metrics.get_ttft().mean
        if tokens < 2 or not all(math.isfinite(value) and value > 0 for value in (throughput, ttft)):
            raise RuntimeError('OpenVINO did not return usable generation and first-token measurements.')
        samples.append({'output_tokens': tokens, 'generation_tokens_per_second': throughput,
                        'time_to_first_token_ms': ttft})
    return {
        'engine': 'openvino-genai', 'target_requested': 'npu', 'evidence': 'measured',
        'model': {'path': str(path), 'name': path.name},
        'generation_tokens_per_second': statistics.mean(s['generation_tokens_per_second'] for s in samples),
        'time_to_first_token_ms': statistics.mean(s['time_to_first_token_ms'] for s in samples),
        'samples': samples, 'runtime': capability, 'prompt': PROMPT,
        'protocol': {'warmup_runs': 1, 'measured_runs': REPETITIONS, 'max_new_tokens': MAX_NEW_TOKENS,
                     'device': 'NPU', 'sampling': False},
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--model')
    args = parser.parse_args(argv)
    result = measure(model_folder(args.model)) if args.model else probe()
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
