"""Pages HTML et réponses JSON fictives pour les tests (aucun appel réseau).

Le balisage reproduit celui observé sur le Guichet-Emplois en novembre 2026.
"""

from __future__ import annotations


def make_article(
    job_id: int,
    title: str = "développeur Web/développeuse Web",
    origin: str = "Guichet-Emplois",
    employer: str = "Exemple inc.",
    location: str = "Québec (QC)",
    salary: str | None = "30,00 $ de l'heure",
    telework: str | None = None,
    date: str = "12 novembre 2026",
) -> str:
    """Une offre telle qu'affichée sur la page de résultats."""
    flags = '<span class="new">Nouveau</span>'
    if telework:
        flags += f'<span class="telework">{telework}</span>'
    if origin == "Guichet-Emplois":
        flags += (
            '<span class="appmethod">Candidature directe</span>'
            '<span class="postedonJB">Publiée sur le Guichet-Emplois'
            '<span class="description"><span class="fa fa-info-circle"></span>'
            "Cette offre d’emploi a été publiée directement par l’employeur.</span></span>"
        )
    salary_html = (
        f'<li class="salary"><span class="fa fa-dollar"></span> Salaire : {salary}</li>'
        if salary
        else ""
    )
    return f"""
<article id="article-{job_id}" class="action-buttons">
  <a href="/rechercheemplois/offredemploi/{job_id};jsessionid=ABC123.jobsearch76?source=searchresults"
     class="resultJobItem">
    <h3 class="title">
      <span class="flag">{flags}</span>
      <span class="job-source job-source-icon-16"><span class="wb-inv">{origin}</span></span>
      <span class="noctitle"> {title}
      </span>
    </h3>
    <ul class="list-unstyled">
      <li class="date">{date}
      </li>
      <li class="business">{employer}</li>
      <li class="location"><span class="fas fa-map-marker-alt"></span>
        <span class="wb-inv">Emplacement</span>
        {location}
      </li>
      {salary_html}
      <li class="source"><span class="job-source"><span class="wb-inv">{origin}</span></span>
        <span class="wb-inv">Numéro de l’offre :</span>
        <span class="fa fa-hashtag"></span>
        {job_id + 9000}</li>
    </ul></a>
  <div class="float job-action"><section class="mfp-hide"><p>Connexion<br>requise</p></section></div>
</article>"""


def make_page(articles: list[str], total: int | None = 3) -> str:
    """Une page de résultats, avec le nombre total d'offres annoncé en haut."""
    count = (
        f'<h2><span class="found" id="results-count">{total}</span> résultats</h2>'
        if total
        else ""
    )
    return f"<html><body>{count}<div id='results'>{''.join(articles)}</div></body></html>"


FIXTURE_PAGE = make_page(
    [
        make_article(101, telework="Sur place"),
        make_article(
            102,
            title="agent/agente de soutien aux utilisateurs",
            origin="Jobillico",
            employer="GolfIn - Saint-Georges",
            location="Saint-Georges (QC)",
            salary="52 000,00 $ à 60 000,00 $ par année",
        ),
        make_article(
            103,
            title="stagiaire en programmation informatique",
            origin="Talent.com",
            employer="Studio Nord",
            location="Montréal (QC)",
            salary=None,
            telework="Hybride",
            date="9 novembre 2026",
        ),
    ]
)


REMOTIVE_PAYLOAD = {
    "total-job-count": 3,
    "jobs": [
        {
            "id": 42,
            "url": "https://remotive.com/remote-jobs/software-dev/intern-42",
            "title": "Software Engineer Intern",
            "company_name": "Example",
            "candidate_required_location": "Canada",
            "job_type": "internship",
            "category": "Software Development",
            "tags": ["Python", "Remote"],
            "publication_date": "2026-11-09T10:00:00",
            "salary": "$20/hour",
            "description": "<p>Build tools with <strong>Python</strong>.</p>",
        },
        {
            "id": 43,
            "url": "https://remotive.com/remote-jobs/software-dev/other-43",
            "title": "Developer",
            "candidate_required_location": "United States",
            "category": "Software Development",
        },
        {
            "id": 44,
            "title": "Technical Writer",
            "candidate_required_location": "Worldwide",
            "category": "Writing",
        },
    ],
}
