import argparse
import os
import sys
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--logdir', default='runs/real_eval')
    parser.add_argument('--num-samples', type=int, default=200)
    args = parser.parse_args()

    try:
        import torch
        from torch.utils.tensorboard import SummaryWriter
        from torchvision import transforms, datasets
        import numpy as np
        from PIL import Image
    except Exception as e:
        print('missing deps:', e); sys.exit(1)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    transform = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
    ])
    if not os.path.isdir(args.data):
        print('data dir not found:', args.data); sys.exit(1)

    dataset = datasets.ImageFolder(args.data, transform=transform)
    if len(dataset)==0:
        print('no samples in data dir'); sys.exit(1)

    loader = torch.utils.data.DataLoader(dataset, batch_size=16, shuffle=False)

    writer = SummaryWriter(args.logdir)

    # try load model
    model = None
    try:
        ckpt = torch.load(args.model, map_location=device)
        if isinstance(ckpt, torch.nn.Module):
            model = ckpt
        elif isinstance(ckpt, dict):
            # try if checkpoint is full module pickled
            if 'model' in ckpt and isinstance(ckpt['model'], torch.nn.Module):
                model = ckpt['model']
            else:
                # can't reconstruct architecture here
                model = None
        else:
            model = None
    except Exception as e:
        print('model load failed:', e)
        model = None

    if model is not None:
        model.to(device)
        model.eval()
        print('model loaded and set to eval')
    else:
        print('no runnable model loaded; will write images and labels only')

    # write class distribution
    from collections import Counter
    label_counts = Counter([label for _,label in dataset.samples])
    for cls, cnt in label_counts.items():
        writer.add_scalar(f'data/class_count/{cls}', cnt, 0)

    total = 0
    correct = 0
    step = 0
    samples_written = 0
    for images, labels in loader:
        if samples_written >= args.num_samples:
            break
        b = images.size(0)
        # write images (first image of batch)
        for i in range(min(b,4)):
            img = images[i]
            writer.add_image(f'real_images/{dataset.classes[labels[i]]}_{i}', img, step)
            samples_written += 1
            if samples_written>=args.num_samples:
                break
        if model is not None:
            images = images.to(device)
            with torch.no_grad():
                try:
                    out = model(images)
                    if isinstance(out, tuple) or isinstance(out, list):
                        out = out[0]
                    preds = out.argmax(dim=1).detach().cpu()
                    correct += (preds==labels).sum().item()
                    total += b
                except Exception as e:
                    print('model inference failed on batch:', e)
                    model = None
        step += 1

    if total>0:
        acc = correct/total
        writer.add_scalar('eval/accuracy', acc, 0)
        print('wrote accuracy', acc)
    else:
        writer.add_text('eval/info', 'model not runnable; images+labels only', 0)

    writer.close()
    print('wrote events to', args.logdir)

if __name__=='__main__':
    main()
