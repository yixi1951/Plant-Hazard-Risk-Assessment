import torch
from scripts.inference_utils import MultiTaskNetwork
import argparse

def export(model_path='best_multitask_model.pth', out_path='best_multitask_model.onnx'):
    device = torch.device('cpu')
    model = MultiTaskNetwork(num_diseases=1, num_severity=3)
    state = torch.load(model_path, map_location=device)
    model.load_state_dict(state)
    model.eval()

    dummy = torch.randn(1, 3, 128, 128)
    torch.onnx.export(
        model,
        dummy,
        out_path,
        opset_version=13,
        dynamo=False,
        input_names=['input'],
        output_names=['disease_logit', 'severity_logits', 'features'],
        dynamic_axes={'input': {0: 'batch'}}
    )
    print('Exported ONNX to', out_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='best_multitask_model.pth')
    parser.add_argument('--out', default='best_multitask_model.onnx')
    args = parser.parse_args()
    export(args.model, args.out)
