from django.conf import settings
import os
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

# ruta del modelo
MODEL_PATH = os.path.join(settings.BASE_DIR, "model_clasificator")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

id2label = model.config.id2label

def predict_tag(text: str):
    tokens = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        logits = model(**tokens).logits
    pred_id = torch.argmax(logits, dim=1).item()
    return id2label[pred_id]