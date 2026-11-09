"""Optional, isolated Intel NPU capability adapter. Never substitutes CPU execution."""
import json

def probe():
    try:
        import openvino as ov
        core=ov.Core()
        devices=list(core.available_devices)
        npu=[d for d in devices if d.split('.')[0]=='NPU']
        try:
            import openvino_genai
            genai=openvino_genai.__version__
        except ImportError: genai=None
        return {'status':'available' if npu and genai else 'unavailable','devices':devices,'npu_devices':npu,'openvino_version':ov.__version__,'genai_version':genai,'message':('NPU runtime detected. Model compilation and architecture support must still be verified.' if npu and genai else 'Requires an Intel NPU driver, OpenVINO NPU device and openvino-genai.'),'benchmark_status':'not_implemented','contract':{'model_format':'OpenVINO IR directory with tokenizer; GGUF is not supported','device':'NPU only; never AUTO or CPU fallback','future_metrics':['get_throughput','get_ttft','get_num_generated_tokens'],'protocol':'One warmup, three measured iterations, fixed prompt and token budget; record versions and perf_metrics. Compile failures are unsupported, never scores.'}}
    except Exception as e: return {'status':'unavailable','benchmark_status':'not_implemented','message':str(e),'devices':[]}

if __name__=='__main__': print(json.dumps(probe()))
