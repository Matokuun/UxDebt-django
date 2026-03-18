from django.conf import settings
import os
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
import torch.nn.functional as F

UX_LABELS = [
    "CLIPPED/OVERLAPPING UI",
    "INCONSISTENT FEEDBACK",
    "POOR ACCESSIBILITY",
    "POOR DISCOVERABILITY",
    "UI INCONSISTENCY",
    "UNDESCRIPTIVE ELEMENT",
    "WRONG DEFAULT VALUE",
]

MODEL_PATH = os.path.join(settings.BASE_DIR, "model_clasificator")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
id2label = model.config.id2label

model.eval()

MODEL_PATH_UX = os.path.join(settings.BASE_DIR, "model_ux_smells")

tokenizer_ux = AutoTokenizer.from_pretrained(MODEL_PATH_UX)
model_ux = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH_UX)
id2label_ux = model_ux.config.id2label

model_ux.eval()

def predict_tag(text: str):
    tokens = tokenizer(text, return_tensors="pt", truncation=True, padding=True)

    with torch.no_grad():
        logits = model(**tokens).logits

    probs = F.softmax(logits, dim=1)[0]  # Convertimos a probabilidades

    top2 = torch.topk(probs, k=2)
    pred_ids = top2.indices.tolist()
    scores = top2.values.tolist()

    return {
        "primary_label": id2label[pred_ids[0]],
        "primary_score": float(scores[0]),
        "secondary_label": id2label[pred_ids[1]],
        "secondary_score": float(scores[1])
    }

def predict_ux_smell(text: str):
    tokens = tokenizer_ux(text,return_tensors="pt",truncation=True,padding=True,max_length=256)

    with torch.no_grad():
        logits = model_ux(**tokens).logits

    probs = F.softmax(logits, dim=1)[0]

    top1_id = torch.argmax(probs).item()
    score = probs[top1_id].item()

    return {
        "label": UX_LABELS[top1_id],
        "score": float(score)
    }