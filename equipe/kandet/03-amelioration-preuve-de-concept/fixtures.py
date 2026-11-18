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


def make_posting(
    title: str = "développeur Web/développeuse Web",
    original_title: str | None = None,
    employer_html: str = (
        '<a href="http://exemple.test" class="external">Mewlogic Inc. '
        '<span class="wb-inv ext-desc"> Ce lien ouvrira dans une nouvelle fenêtre</span></a>'
    ),
    description: str = (
        "Études: Baccalauréat. Informatique. Tâches: Coordonner les projets informatiques. "
        "Expérience: 5 ans ou plus."
    ),
    salary_html: str = (
        '<span property="minValue" content="43,27">43,27</span>'
        '<span property="currency" content="CAD" class="hidden">$</span>'
        '<span property="unitText" class="hidden">HOUR</span> de l’heure'
    ),
    valid_through: str | None = "2026-12-07",
    with_requirements: bool = True,
    external_link: str | None = None,
) -> str:
    """Une fiche d'offre réduite, avec les mêmes balises RDFa que le vrai site."""
    original = (
        '<p class="source-title"><span class="source-title-inner">'
        f'<span class="orig-title-label">Appellation affichée sur Jobillico - </span>{original_title}'
        "</span></p>"
        if original_title
        else ""
    )
    requirements = (
        """
  <div class="job-posting-detail-requirements"><div id="comparisonchart">
    <h4>Langues</h4>
    <p property="qualification">Anglais</p>
    <h4>Éducation</h4>
    <ul property="educationRequirements qualification" class="csvlist">
      <li><span>Baccalauréat</span></li>
      <li>ou expérience équivalente</li>
      <li>Informatique</li>
    </ul>
    <h4>Expérience</h4>
    <p property="experienceRequirements qualification"><span>5 ans ou plus</span></p>
    <div id="jobOverview-2" property="responsibilities">
      <h3>Responsabilités</h3>
      <h4>Tâches</h4>
      <ul class="csvlist">
        <li><span>Coordonner les projets informatiques</span></li>
        <li><span>Évaluer des logiciels d’application et résoudre des problèmes</span></li>
      </ul>
    </div>
  </div></div>"""
        if with_requirements
        else ""
    )
    link = (
        f'<a id="externalJobLink" class="btn btn-primary" href="{external_link}">'
        "<span>Voir l’offre d’emploi complète sur</span> Jobillico</a>"
        if external_link
        else ""
    )
    expiry = (
        f'<h3>Publiée jusqu’au</h3><p property="validThrough">{valid_through}\n<span class="timepickler"></span></p>'
        if valid_through
        else ""
    )
    return f"""<html><body><main property="mainContentOfPage" typeof="JobPosting">
  <h1 property="name" class="title"><span property="title">{title} </span></h1>
  {original}
  <p class="date-business"><span property="datePosted" class="date"> Publiée le 16 novembre 2026 </span>
    <span class="business"><span class="wb-inv">Renseignements sur l’employeur</span>
    <span property="hiringOrganization" typeof="Organization"><span property="name">{employer_html}</span></span></span></p>
  {link}
  <h2 class="subtitle">Renseignements sur l’emploi</h2>
  <span class="hidden" property="description">{description}</span>
  <ul class="job-posting-brief">
    <li><span class="wb-inv">Emplacement</span><span property="joblocation" typeof="Place">
      <span class="city" property="address" typeof="PostalAddress"><span property="addressLocality">Vaudreuil-Dorion</span>,
      <span property="addressRegion">QC</span><span property="postalCode">J7V 0M7</span></span></span></li>
    <li><span class="wb-inv">Salaire</span><span property="baseSalary" typeof="MonetaryAmount">
      <span property="value" typeof="QuantitativeValue">{salary_html}</span></span></li>
    <li><span class="wb-inv">Conditions d’emploi</span>
      <span property="employmentType" class="attribute-value">Permanent<span class="attribute-value">Temps plein</span></span></li>
    <li><span property="specialCommitments" class="attribute-value">Jour, Horaire flexible</span></li>
    <li><span class="fa fa-calendar"></span>Débute dès le&nbsp;2027-01-15</li>
  </ul>
  {requirements}
  {expiry}
</main></body></html>"""


# Fiche d'une offre Jobillico : description en HTML encodé deux fois, pas d'exigences.
PARTNER_POSTING = make_posting(
    title="architecte d'applications",
    original_title="Architecte d?ordinateur quantique Niveau 1",
    employer_html="<strong>Nord Quantique</strong>",
    description=(
        "&lt;p&gt;&lt;strong&gt;Poste offert&lt;/strong&gt;&lt;/p&gt;"
        "&lt;p&gt;Vous ferez partie d?une organisation en croissance.&lt;/p&gt;"
    ),
    salary_html=(
        '<span property="minValue" content="123\xa0000">123 000</span> à '
        '<span property="maxValue" content="140\xa0000">140 000</span>'
        '<span property="unitText" class="hidden">YEAR</span> par année'
    ),
    with_requirements=False,
    external_link="https://www.jobillico.com/fr/offre-d-emploi/nord-quantique/architecte/17284262?ji_visitsrc=136",
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
