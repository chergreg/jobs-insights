"""Tests hors ligne de outils.py (aucun appel réseau : session, horloge et attente simulées).

Depuis la racine du dépôt :
    python -m unittest discover -s equipe/dan/livrable3 -p "test_*.py" -v
"""

import tempfile
import unittest
from pathlib import Path
from urllib.robotparser import RobotFileParser

from requests.structures import CaseInsensitiveDict

from outils import AccesRefuse, Client, Robots

FIXTURES = Path(__file__).with_name("fixtures")
CB = "https://www.careerbeacon.com"
GE = "https://www.guichetemplois.gc.ca"


class TestRobotsCareerBeacon(unittest.TestCase):
    """Le vrai robots.txt de CareerBeacon (lu le 2026-11-16)."""

    def setUp(self):
        self.texte = (FIXTURES / "robots_careerbeacon.txt").read_text(encoding="utf-8")
        self.robots = Robots(self.texte)

    def test_recherche_et_fiches_permises(self):
        self.assertTrue(self.robots.autorise(CB + "/fr/rechercher/jobs-in-New-Brunswick?page=2"))
        self.assertTrue(self.robots.autorise(CB + "/en/job/2190965/nb-power/engineer/fredericton-nb"))

    def test_pages_interdites(self):
        for chemin in ("/jobs/123", "/en/apply/2190965", "/fr/appliquer/1", "/rss/jobs", "/login/"):
            with self.subTest(chemin=chemin):
                self.assertFalse(self.robots.autorise(CB + chemin))

    def test_joker_filtre_salaire(self):
        url = CB + "/fr/rechercher/jobs-in-New-Brunswick?filter-salary_min=40000"
        self.assertFalse(self.robots.autorise(url))
        self.assertFalse(self.robots.autorise(CB + "/en/search/x?a=1&filter-est_salary_max=9"))

    def test_robotparser_de_python_se_trompe_sur_le_joker(self):
        """Pourquoi on n'utilise pas urllib.robotparser : il autorise cette URL interdite."""
        python = RobotFileParser()
        python.parse(self.texte.splitlines())
        url = CB + "/fr/rechercher/jobs-in-New-Brunswick?filter-salary_min=40000"
        self.assertTrue(python.can_fetch("jobs-insights-dan", url))
        self.assertFalse(self.robots.autorise(url))

    def test_groupe_dun_autre_robot_ignore_pour_nous(self):
        self.assertTrue(self.robots.autorise(CB + "/fr/rechercher/x"))     # ia_archiver : Disallow /
        robots_archiver = Robots(self.texte, user_agent="ia_archiver/1.0")
        self.assertFalse(robots_archiver.autorise(CB + "/fr/rechercher/x"))

    def test_pas_de_crawl_delay(self):
        self.assertIsNone(self.robots.crawl_delay)


class TestRobotsRegles(unittest.TestCase):
    def test_regle_la_plus_longue_gagne(self):
        robots = Robots("User-agent: *\nDisallow: /prive\nAllow: /prive/public\n")
        self.assertFalse(robots.autorise("https://x/prive/secret"))
        self.assertTrue(robots.autorise("https://x/prive/public/page"))

    def test_allow_gagne_a_egalite(self):
        robots = Robots("User-agent: *\nDisallow: /page\nAllow: /page\n")
        self.assertTrue(robots.autorise("https://x/page"))

    def test_dollar_fin_url(self):
        robots = Robots("User-agent: *\nDisallow: /*.pdf$\n")
        self.assertFalse(robots.autorise("https://x/doc/a.pdf"))
        self.assertTrue(robots.autorise("https://x/doc/a.pdf?v=2"))

    def test_groupe_qui_nous_nomme_prioritaire(self):
        texte = "User-agent: *\nDisallow: /\n\nUser-agent: Jobs-Insights-Dan\nDisallow: /admin\n"
        robots = Robots(texte)
        self.assertTrue(robots.autorise("https://x/offres"))
        self.assertFalse(robots.autorise("https://x/admin/1"))

    def test_crawl_delay_lu(self):
        robots = Robots("User-agent: *\nCrawl-delay: 5\nDisallow: /admin\n")
        self.assertEqual(robots.crawl_delay, 5.0)

    def test_fichier_vide_tout_permis(self):
        robots = Robots("")
        self.assertTrue(robots.autorise("https://x/nimporte"))
        self.assertIsNone(robots.crawl_delay)

    def test_disallow_vide_ne_bloque_rien(self):
        self.assertTrue(Robots("User-agent: *\nDisallow:\n").autorise("https://x/a"))


# --- Client -------------------------------------------------------------------------

class FausseReponse:
    def __init__(self, code=200, texte="", entetes=None):
        self.status_code = code
        self.text = texte
        self.headers = CaseInsensitiveDict(entetes or {})
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FausseSession:
    """Répond à partir d'un dictionnaire url → FausseReponse et note chaque appel."""

    def __init__(self, reponses):
        self.reponses = reponses
        self.appels = []

    def get(self, url, headers=None, timeout=None):
        self.appels.append((url, headers))
        return self.reponses.get(url, FausseReponse(404))


class FausseHorloge:
    def __init__(self):
        self.t = 1000.0
        self.attentes = []

    def __call__(self):
        return self.t

    def attendre(self, secondes):
        self.attentes.append(round(secondes, 3))
        self.t += secondes


class TestClient(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.horloge = FausseHorloge()
        self.temps_reel = [5_000_000.0]

    def tearDown(self):
        self.dossier.cleanup()

    def client(self, reponses, cache=False):
        self.session = FausseSession(reponses)
        return Client(
            session=self.session,
            attendre=self.horloge.attendre,
            horloge=self.horloge,
            maintenant=lambda: self.temps_reel[0],
            cache_dossier=Path(self.dossier.name) if cache else None,
        )

    def test_user_agent_honnete_envoye(self):
        client = self.client({GE + "/robots.txt": FausseReponse(200, ""), GE + "/a": FausseReponse(200, "ok")})
        client.telecharger(GE + "/a")
        self.assertTrue(all("jobs-insights-dan" in h["User-Agent"] for _, h in self.session.appels))

    def test_crawl_delay_respecte_entre_deux_pages(self):
        client = self.client({
            GE + "/robots.txt": FausseReponse(200, "User-agent: *\nCrawl-delay: 5\n"),
            GE + "/p1": FausseReponse(200, "1"),
            GE + "/p2": FausseReponse(200, "2"),
        })
        client.telecharger(GE + "/p1")
        client.telecharger(GE + "/p2")
        self.assertEqual(self.horloge.attentes, [5.0, 5.0])   # après robots.txt, puis après p1

    def test_delai_minimum_si_pas_de_crawl_delay(self):
        client = self.client({CB + "/robots.txt": FausseReponse(200, ""), CB + "/a": FausseReponse(200, "")})
        client.telecharger(CB + "/a")
        self.assertEqual(self.horloge.attentes, [2.0])

    def test_robots_interdit_aucune_requete_page(self):
        client = self.client({CB + "/robots.txt": FausseReponse(200, "User-agent: *\nDisallow: /jobs/\n")})
        with self.assertRaises(AccesRefuse) as ctx:
            client.telecharger(CB + "/jobs/1")
        self.assertIn("robots.txt interdit", str(ctx.exception))
        self.assertEqual([u for u, _ in self.session.appels], [CB + "/robots.txt"])

    def test_403_cloudflare_arret_propre(self):
        client = self.client({
            CB + "/robots.txt": FausseReponse(200, ""),
            CB + "/fr/rechercher/x": FausseReponse(403, "", {"Server": "cloudflare", "CF-RAY": "abc"}),
        })
        with self.assertRaises(AccesRefuse) as ctx:
            client.telecharger(CB + "/fr/rechercher/x")
        self.assertIn("Cloudflare", str(ctx.exception))
        self.assertIn("sans contournement", str(ctx.exception))

    def test_429_indique_retry_after(self):
        client = self.client({
            GE + "/robots.txt": FausseReponse(200, ""),
            GE + "/a": FausseReponse(429, "", {"Retry-After": "30"}),
        })
        with self.assertRaises(AccesRefuse) as ctx:
            client.telecharger(GE + "/a")
        self.assertIn("429", str(ctx.exception))
        self.assertIn("30", str(ctx.exception))

    def test_401_connexion_requise(self):
        client = self.client({GE + "/robots.txt": FausseReponse(200, ""), GE + "/a": FausseReponse(401)})
        with self.assertRaisesRegex(AccesRefuse, "connexion"):
            client.telecharger(GE + "/a")

    def test_robots_absent_404_tout_permis(self):
        client = self.client({GE + "/a": FausseReponse(200, "ok")})       # robots.txt → 404
        self.assertEqual(client.telecharger(GE + "/a"), "ok")

    def test_robots_refuse_403_arret(self):
        client = self.client({GE + "/robots.txt": FausseReponse(403)})
        with self.assertRaises(AccesRefuse):
            client.telecharger(GE + "/a")

    def test_robots_erreur_serveur_arret(self):
        client = self.client({GE + "/robots.txt": FausseReponse(503)})
        with self.assertRaisesRegex(AccesRefuse, "indisponible"):
            client.telecharger(GE + "/a")

    def test_cache_evite_la_requete(self):
        client = self.client({GE + "/robots.txt": FausseReponse(200, ""), GE + "/a": FausseReponse(200, "page")},
                             cache=True)
        self.assertEqual(client.telecharger(GE + "/a"), "page")
        nb_appels = len(self.session.appels)
        attentes = list(self.horloge.attentes)
        self.assertEqual(client.telecharger(GE + "/a"), "page")
        self.assertEqual(len(self.session.appels), nb_appels)          # aucune nouvelle requête
        self.assertEqual(self.horloge.attentes, attentes)              # aucune attente

    def test_cache_expire_apres_24h(self):
        client = self.client({GE + "/robots.txt": FausseReponse(200, ""), GE + "/a": FausseReponse(200, "page")},
                             cache=True)
        client.telecharger(GE + "/a")
        self.temps_reel[0] += 24 * 3600 + 1
        client.telecharger(GE + "/a")
        self.assertEqual([u for u, _ in self.session.appels].count(GE + "/a"), 2)

    def test_cache_desactivable(self):
        client = self.client({GE + "/robots.txt": FausseReponse(200, ""), GE + "/a": FausseReponse(200, "page")},
                             cache=True)
        client.telecharger(GE + "/a", utiliser_cache=False)
        client.telecharger(GE + "/a", utiliser_cache=False)
        self.assertEqual([u for u, _ in self.session.appels].count(GE + "/a"), 2)
        self.assertEqual(list(Path(self.dossier.name).iterdir()), [])  # rien écrit


if __name__ == "__main__":
    unittest.main()
