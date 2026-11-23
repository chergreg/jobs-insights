import requests
from bs4 import BeautifulSoup

url = "https://emplois.ca.indeed.com/jobs?q=stage+informatique&l=Qu%C3%A9bec"

reponse = requests.get(url, timeout=15)

print("Statut HTTP :", reponse.status_code)
print("Taille de la page :", len(reponse.text))