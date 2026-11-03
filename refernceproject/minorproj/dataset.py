import kagglehub

path = kagglehub.dataset_download("aniruddhawankhede/oceanplasticpollution")

print("Dataset location:", path)
import os

print(os.listdir(path))