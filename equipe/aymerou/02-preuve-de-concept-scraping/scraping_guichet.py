
import requests
from bs4 import BeautifulSoup

url = "https://www.guichetemplois.gc.ca/jobsearch/jobsearch?searchstring=informatique&locationstring=&locationparam=&sort=M"

reponse = requests.get(url, timeout=15)

print("Statut HTTP :", reponse.status_code)

if reponse.status_code == 200:
    soup = BeautifulSoup(reponse.text, "html.parser")
    offres = soup.select("article")

print("Nombre d'éléments trouvés :", len(offres))

for offre in offres[:5]:
    titre = offre.find("h3")

    if titre:
        print(titre.get_text(strip=True))
    print("Titre de la page :", soup.title.get_text(strip=True) if soup.title else "Introuvable")
else:
    print("Impossible de récupérer la page.")
