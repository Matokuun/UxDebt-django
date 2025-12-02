from django.conf import settings
import os
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
import torch.nn.functional as F

MODEL_PATH = os.path.join(settings.BASE_DIR, "model_clasificator")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
id2label = model.config.id2label


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