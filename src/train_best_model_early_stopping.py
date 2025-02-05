import torch
import torch.nn as nn
import wandb
from types import SimpleNamespace
from model import GAT  
from train_and_test import train, validate
from data_utils import build_optimizer, build_dataloaders, set_seed

def train_best_model_early_stopping(graphs, labels, dataset_name, patience, new_num_epochs):
    # Initialize wandb
    wandb.init(project=f'graph-classification-{dataset_name}')

    # Load the best model and config
    checkpoint = torch.load(f'best_model_{dataset_name}.pth')

    # Load the config and update num_epochs
    config = SimpleNamespace(**checkpoint['config'])
    config.num_epochs = new_num_epochs

    print(f"Running with config: {config}")

    # Set random seed
    set_seed(config.random_state)

    # Build data loaders
    train_loader, val_loader, _ = build_dataloaders(graphs, labels, config)

    # Model, criterion, and optimizer
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = GAT(
        in_channels=config.in_channels,
        out_channels=config.out_channels,
        num_heads=config.num_heads,
        num_classes=2
    ).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])

    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(model, config.optimizer, config.learning_rate, config.weight_decay)

    # Watch the model with wandb
    wandb.watch(model, log="all", log_freq=10)

    # Early stopping parameters
    best_val_f1 = 0.0
    epochs_without_improvement = 0

    # Train the model with early stopping
    for epoch in range(config.num_epochs):
        train_loss, train_accuracy, train_f1 = train(train_loader, model, criterion, optimizer, device)
        val_loss, val_accuracy, val_f1 = validate(val_loader, model, criterion, device)

        # Log metrics
        wandb.log({
            'epoch': epoch + 1,
            'train_loss': train_loss,
            'train_accuracy': train_accuracy,
            'train_f1': train_f1,
            'val_loss': val_loss,
            'val_accuracy': val_accuracy,
            'val_f1': val_f1,
        })

        # Check for improvement
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            epochs_without_improvement = 0

            # Save the best model
            torch.save({
                'model_state_dict': model.state_dict(),
                'config': vars(config)
            }, f'final_model_{dataset_name}.pth')
            artifact = wandb.Artifact(f'final_model_{dataset_name}', type='model')
            artifact.add_file(f'final_model_{dataset_name}.pth')
            wandb.log_artifact(artifact)
        else:
            epochs_without_improvement += 1

        # Early stopping
        if epochs_without_improvement >= patience:
            print("Early stopping triggered.")
            break

    del model
    del optimizer
    del criterion
    torch.cuda.empty_cache()
    wandb.finish()
