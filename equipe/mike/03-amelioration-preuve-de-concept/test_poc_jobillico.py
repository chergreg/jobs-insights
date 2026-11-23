"""Tests hors ligne : aucun appel à Jobillico, on lui donne de fausses pages.

Lancement :  python -m unittest test_poc_jobillico.py -v
"""

import unittest

import poc_jobillico as poc

PAGE_1 = """
<a href="/fr/offre-d-emploi/fop/developpeur-int.-/17549427">Développeur (int.)</a>
<a href="/fr/offre-d-emploi/fop/developpeur-int.-/17549427?src=liste">Voir l'offre</a>
<a href="/fr/offre-d-emploi/fop/developpeur-sr.-/17549442">Développeur (sr.)</a>
"""
PAGE_2 = """
<a href="/fr/offre-d-emploi/fop/developpeur-sr.-/17549442">Développeur (sr.)</a>
<a href="/fr/offre-d-emploi/exemple/analyste/17600001">Analyste</a>
"""
PAGE_3 = PAGE_2  # rien de nouveau : la pagination doit s'arrêter

OFFRE = """<script type="application/ld+json">
{"@type":"JobPosting","title":"Développeur (int.)","datePosted":"2026-10-20T08:00:00",
 "employmentType":"FULL_TIME",
 "hiringOrganization":{"name":"FOP Experts Conseils inc."},
 "jobLocation":{"address":{"addressLocality":"Québec"}},
 "description":"<p>Concevoir et <strong>tester</strong> des logiciels.</p>"}
</script>"""
OFFRE_INCOMPLETE = """<script type="application/ld+json">{ pas du JSON }</script>
<script type="application/ld+json">{"@type":"JobPosting","title":"Analyste"}</script>"""


class RobotsPermissif:
    def can_fetch(self, agent, url):
        return True


class RobotsInterdit:
    def can_fetch(self, agent, url):
        return False


class RobotsSansOffres:
    """Autorise la recherche mais interdit les pages d'offres."""
    def can_fetch(self, agent, url):
        return "offre-d-emploi" not in url


class RobotsLent(RobotsPermissif):
    def crawl_delay(self, agent):
        return 10


def faux_site(pages):
    appels = []

    def telecharger(url):
        appels.append(url)
        return pages[url]
    return telecharger, appels


class TestLecture(unittest.TestCase):
    def test_adresse_avec_numero_de_page(self):
        self.assertTrue(poc.url_recherche("développeur", "Québec, QC", 2).endswith("&ipg=2"))

    def test_liens_sans_doublon(self):
        self.assertEqual(len(poc.extraire_liens(PAGE_1)), 2)

    def test_offre_complete(self):
        o = poc.lire_offre(OFFRE, "url")
        self.assertEqual(o["company"], "FOP Experts Conseils inc.")
        self.assertEqual(o["city"], "Québec")
        self.assertEqual(o["date_posted"], "2026-10-20")
        self.assertEqual(o["description"], "Concevoir et tester des logiciels.")

    def test_rien_n_est_invente(self):
        o = poc.lire_offre(OFFRE_INCOMPLETE, "url")
        self.assertEqual(o["title"], "Analyste")
        self.assertIsNone(o["company"])  # Mamadou mettait « Employeur Jobillico »
        self.assertIsNone(o["city"])     # Mamadou mettait « Québec »

    def test_json_ld_en_graph(self):
        html = ('<script type="application/ld+json">{"@graph":[{"@type":"WebPage"},'
                '{"@type":["JobPosting"],"title":"Technicien"}]}</script>')
        self.assertEqual(poc.lire_offre(html, "url")["title"], "Technicien")

    def test_pas_de_json_ld(self):
        self.assertIsNone(poc.lire_offre("<p>Offre expirée</p>", "url"))


class TestPagination(unittest.TestCase):
    def pages(self):
        p = {poc.url_recherche("développeur", "Québec, QC", n): h
             for n, h in [(1, PAGE_1), (2, PAGE_2), (3, PAGE_3)]}
        for path in ["/fr/offre-d-emploi/fop/developpeur-int.-/17549427",
                     "/fr/offre-d-emploi/fop/developpeur-sr.-/17549442",
                     "/fr/offre-d-emploi/exemple/analyste/17600001"]:
            p[poc.BASE + path] = OFFRE
        return p

    def test_lit_plusieurs_pages_sans_doublon(self):
        telecharger, appels = faux_site(self.pages())
        offres = poc.scrape_jobillico(max_pages=5, robots=RobotsPermissif(),
                                      telecharger=telecharger, pause=0)
        self.assertEqual(len(offres), 3)  # 2 offres en page 1 + 1 nouvelle en page 2
        pages_lues = [u for u in appels if "recherche-emploi" in u]
        self.assertEqual(len(pages_lues), 3)  # s'arrête en page 3 : rien de nouveau

    def test_robots_interdit(self):
        telecharger, appels = faux_site(self.pages())
        offres = poc.scrape_jobillico(robots=RobotsInterdit(), telecharger=telecharger, pause=0)
        self.assertEqual(offres, [])
        self.assertEqual(appels, [])  # aucune requête envoyée

    def test_robots_interdit_les_offres(self):
        telecharger, appels = faux_site(self.pages())
        offres = poc.scrape_jobillico(max_pages=1, robots=RobotsSansOffres(),
                                      telecharger=telecharger, pause=0)
        self.assertEqual(offres, [])
        self.assertFalse(any("offre-d-emploi" in u for u in appels))  # aucune offre ouverte

    def test_page_en_erreur_garde_les_offres(self):
        pages = self.pages()
        del pages[poc.url_recherche("développeur", "Québec, QC", 2)]  # la page 2 « plante »
        telecharger, _ = faux_site(pages)
        offres = poc.scrape_jobillico(max_pages=3, robots=RobotsPermissif(),
                                      telecharger=telecharger, pause=0)
        self.assertEqual(len(offres), 2)  # les 2 offres de la page 1 sont gardées

    def test_pause_entre_les_pages(self):
        pauses = []
        telecharger, _ = faux_site(self.pages())
        original = poc.time.sleep
        poc.time.sleep = pauses.append
        try:
            poc.scrape_jobillico(max_pages=3, robots=RobotsPermissif(),
                                 telecharger=telecharger, pause=5)
        finally:
            poc.time.sleep = original
        # 2 pauses avant les pages 2 et 3, puis 1 avant chacune des 3 offres
        self.assertEqual(pauses, [5] * 5)

    def test_robots_lu_avec_notre_user_agent(self):
        regles = "User-agent: *\nDisallow: /recherche-emploi\n"
        appels = []

        def telecharger(url):
            appels.append(url)
            return regles
        robots = poc.preparer_robots(telecharger)
        self.assertEqual(appels, [poc.BASE + "/robots.txt"])  # lu par notre fonction
        self.assertFalse(robots.can_fetch(poc.HEADERS["User-Agent"],
                                          poc.url_recherche("x", "y", 1)))

    def test_robots_illisible_tout_interdit(self):
        def telecharger(url):
            raise OSError("réseau coupé")
        robots = poc.preparer_robots(telecharger)
        self.assertFalse(robots.can_fetch(poc.HEADERS["User-Agent"], poc.BASE + "/"))

    def test_crawl_delay_respecte(self):
        pauses = []
        telecharger, _ = faux_site(self.pages())
        original = poc.time.sleep
        poc.time.sleep = pauses.append  # on note les pauses au lieu d'attendre
        try:
            poc.scrape_jobillico(max_pages=1, robots=RobotsLent(),
                                 telecharger=telecharger, pause=5)
        finally:
            poc.time.sleep = original
        self.assertTrue(pauses)
        self.assertTrue(all(p == 10 for p in pauses))  # 10 s demandées, pas 5


class TestRobotsJobillico(unittest.TestCase):
    """Règles réelles relevées dans le robots.txt de Jobillico le 23 nov. 2026."""

    REGLES = (
        "User-agent: *\n"
        "Disallow: /*&ipg=          # to prevent crawling deep pagination\n"
        "Allow: /*&ipg=1$\n"
        "Allow: /*&ipg=1&\n"
        "Disallow: *skwd=&scty=&\n"
    )
    AGENT = poc.HEADERS["User-Agent"]

    def setUp(self):
        self.robots = poc.RobotsAvecJokers(self.REGLES)

    def autorise(self, page=None, url=None):
        url = url or poc.url_recherche("développeur", "Québec, QC", page)
        return self.robots.can_fetch(self.AGENT, url)

    def test_page_1_autorisee(self):
        self.assertTrue(self.autorise(page=1))

    def test_pages_2_et_suivantes_interdites(self):
        for page in (2, 3, 10):
            self.assertFalse(self.autorise(page=page), f"page {page}")

    def test_ipg_1_suivi_d_un_autre_parametre(self):
        self.assertTrue(self.autorise(url=poc.BASE + "/recherche-emploi?skwd=a&ipg=1&sort=date"))

    def test_page_12_pas_confondue_avec_page_1(self):
        self.assertFalse(self.autorise(url=poc.BASE + "/recherche-emploi?skwd=a&ipg=12"))

    def test_recherche_vide_interdite(self):
        self.assertFalse(self.autorise(url=poc.BASE + "/recherche-emploi?skwd=&scty=&ipg=1"))

    def test_offres_autorisees(self):
        self.assertTrue(self.autorise(url=poc.BASE + "/fr/offre-d-emploi/fop/developpeur/17549427"))

    def test_robotparser_standard_se_trompe(self):
        """Preuve du problème : la bibliothèque standard autorise la page 2."""
        import urllib.robotparser
        standard = urllib.robotparser.RobotFileParser()
        standard.parse(self.REGLES.splitlines())
        self.assertTrue(standard.can_fetch(self.AGENT, poc.url_recherche("développeur", "Québec, QC", 2)))

    def test_la_collecte_s_arrete_a_la_page_1(self):
        pages = {poc.url_recherche("développeur", "Québec, QC", 1):
                 '<a href="/fr/offre-d-emploi/fop/dev/1">x</a>',
                 poc.BASE + "/fr/offre-d-emploi/fop/dev/1": OFFRE}
        appels = []

        def telecharger(url):
            appels.append(url)
            return pages[url]
        offres = poc.scrape_jobillico(max_pages=3, robots=self.robots,
                                      telecharger=telecharger, pause=0)
        self.assertEqual(len(offres), 1)
        self.assertFalse(any("ipg=2" in u for u in appels))  # la page 2 n'est jamais demandée

    def test_crawl_delay_lu_dans_le_fichier(self):
        robots = poc.RobotsAvecJokers("User-agent: *\nCrawl-delay: 7\n")
        self.assertEqual(robots.crawl_delay(self.AGENT), 7.0)


if __name__ == "__main__":
    unittest.main()
