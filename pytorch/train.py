#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import torch
import argparse
import torchvision

import numpy as np
import pandas as pd
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms

from tqdm import tqdm
from PIL import Image
from torch.utils.data import Dataset, DataLoader

DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def get_args():
    """Arguments parser."""
    parser = argparse.ArgumentParser(description='Pytorch skeleton.')
    parser.add_argument('--train-csv', required=True,
                        help='Path to train.csv.')
    parser.add_argument('--valid-csv', required=True,
                        help='Path to valid.csv.')
    parser.add_argument('--lr', type=float, default=1e-3,
                        help='Start learning rate value.')
    parser.add_argument('--bs', type=int, default=4,
                        help='Batch-size.')
    parser.add_argument('--workers', type=int, default=2,
                        help='Workers for every dataloader.')
    parser.add_argument('--momentum', type=float, default=0.9,
                        help='SGD momentum.')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of train epochs.')
    parser.add_argument('--resize-to', type=int, default=256,
                        help='Resize train image before crop.')
    parser.add_argument('--save-to', required=True,
                        help='Path for save a trained model and optim.')
    parser.add_argument('--load-from',
                        help='Path to dir with "model.pth" and "optim.pth".')
    parser.add_argument('--pretrained', action='store_true',
                        help='Create pretrained model.')

    args = parser.parse_args()
    if not os.path.exists(args.save_to):
        try:
            os.mkdir(args.save_to)
            print('\n"save-to" dir has been created.')
        except Exception as e:
            print('"save-to" does not exist and can\'t be created:', e)
            exit(1)

    return args


class SeedlingDataset(Dataset):
    def __init__(self, paths, labels, transform):
        self.paths = paths
        self.labels = labels
        self.transform = transform

    def __getitem__(self, idx):
        img = self.transform(Image.open(self.paths[idx]).convert('RGB'))
        return img, self.labels[idx]

    def __len__(self):
        return len(self.labels)


def train(model, optimizer, criterion,
          train_dl, valid_dl, epochs=10, save_to=None):
    best_loss_train = np.inf
    best_loss_valid = np.inf
    best_acc_train = 0.0
    best_acc_valid = 0.0

    for ep in np.arange(epochs):
        # train
        total = 0
        correct = 0
        running_loss = 0.0
        print('\nEpoch {} / {}'.format(ep + 1, epochs))

        model.train()
        for i, data in tqdm(enumerate(train_dl, 0)):
            optimizer.zero_grad()

            inputs, labels = data
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            outputs = model(inputs)

            _, predict = torch.max(outputs, 1)
            total += list(labels.size())[0]
            correct += (predict == labels).sum().item()

            loss = criterion(outputs, labels)
            running_loss += loss.item()

            loss.backward()
            optimizer.step()

        if running_loss < best_loss_train:
            best_loss_train = running_loss
            torch.save(model.state_dict(),
                       os.path.join(save_to, 'model_best_loss_train.pth'))
            torch.save(optimizer.state_dict(),
                       os.path.join(save_to, 'optim_best_loss_train.pth'))

        running_acc = 100 * correct / total
        if running_acc > best_acc_train:
            best_acc_train = running_acc
            torch.save(model.state_dict(),
                       os.path.join(save_to, 'model_best_acc_train.pth'))
            torch.save(optimizer.state_dict(),
                       os.path.join(save_to, 'optim_best_acc_train.pth'))

        print('Train loss:', running_loss)
        print('Train acc:', running_acc)

        # valid
        total = 0
        correct = 0
        running_loss = 0.0
        model.eval()
        with torch.no_grad():
            for i, data in tqdm(enumerate(valid_dl, 0)):
                inputs, labels = data
                inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
                outputs = model(inputs)

                _, predict = torch.max(outputs, 1)
                total += list(labels.size())[0]
                correct += (predict == labels).sum().item()

                loss = criterion(outputs, labels)
                running_loss += loss.item()

        if running_loss < best_loss_valid:
            best_loss_valid = running_loss
            torch.save(model.state_dict(),
                       os.path.join(save_to, 'model_best_loss_valid.pth'))
            torch.save(optimizer.state_dict(),
                       os.path.join(save_to, 'optim_best_loss_valid.pth'))

        running_acc = 100 * correct / total
        if running_acc > best_acc_valid:
            best_acc_valid = running_acc
            torch.save(model.state_dict(),
                       os.path.join(save_to, 'model_best_acc_valid.pth'))
            torch.save(optimizer.state_dict(),
                       os.path.join(save_to, 'optim_best_acc_valid.pth'))

        print('Valid loss:', running_loss)
        print('Valid acc:', running_acc)


def main():
    args = get_args()
    train_df = pd.read_csv(args.train_csv).to_numpy()
    valid_df = pd.read_csv(args.valid_csv).to_numpy()
    train_paths = train_df[:, 0]
    valid_paths = valid_df[:, 0]
    train_classes = train_df[:, 1]
    valid_classes = valid_df[:, 1]

    # process classes into classes_ids
    classes_mp = {x: y for x, y in zip(list(set(train_classes)),
                                       np.arange(len(set(train_classes))))}
    train_labels = [classes_mp[name] for name in train_classes]
    valid_labels = [classes_mp[name] for name in valid_classes]

    # prepare dataloaders
    input_img_size = 224  # input size for ResNet
    train_trans = transforms.Compose([
        transforms.Resize((input_img_size, input_img_size)),
        # transforms.Resize(args.resize_to),
        # transforms.RandomResizedCrop(input_img_size),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    valid_trans = transforms.Compose([
        transforms.Resize((input_img_size, input_img_size)),
        # transforms.Resize(args.resize_to),
        # transforms.CenterCrop(input_img_size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    train_ds = SeedlingDataset(train_paths, train_labels, train_trans)
    valid_ds = SeedlingDataset(valid_paths, valid_labels, valid_trans)
    train_dl = DataLoader(
        train_ds, batch_size=args.bs, shuffle=True, num_workers=args.workers
    )
    valid_dl = DataLoader(
        valid_ds, batch_size=args.bs, shuffle=False, num_workers=args.workers
    )

    # setup nn
    criterion = nn.CrossEntropyLoss()
    model = torchvision.models.resnet18(num_classes=len(classes_mp.keys()))
    model.to(DEVICE)
    optimizer = optim.Adam(model.parameters(), args.lr)

    if args.load_from is not None:
        model_path = os.path.join(args.load_from, 'model.pth')
        optim_path = os.path.join(args.load_from, 'optim.pth')
        if os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path))
        else:
            print('WARNING: model path not found.')
            if args.pretrained:
                model_weights = torchvision.models.resnet18(True).state_dict()
                del model_weights['fc.bias']
                del model_weights['fc.weight']
                model.load_state_dict(model_weights, strict=False)

        if os.path.exists(optim_path):
            optimizer.load_state_dict(torch.load(optim_path))
        else:
            print('WARNING: optim path not found.')
    elif args.pretrained:
        model_weights = torchvision.models.resnet18(True).state_dict()
        del model_weights['fc.bias']
        del model_weights['fc.weight']
        model.load_state_dict(model_weights, strict=False)

    # run training
    train(
        model,
        optimizer,
        criterion,
        train_dl,
        valid_dl,
        args.epochs,
        args.save_to
    )
    print('Done!')


if __name__ == '__main__':
    main()