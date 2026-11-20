// Comparaison d'un CV avec les offres, dans le navigateur.
// Même calcul que candidature.py ; les expressions viennent de competences.py (REGLES).
function creerComparateur(REGLES) {
  const simple = (t) => String(t || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const technos = REGLES.technologies.map(([nom, src]) => [nom, new RegExp(src, "iu")]);
  const competences = REGLES.competences.map(([nom, src]) => [nom, new RegExp(src, "u")]);
  const expDescription = new RegExp(REGLES.experienceDescription, "u");
  const etudiant = new RegExp(REGLES.etudiant, "u");
  const stageRecherche = new RegExp(REGLES.stageRecherche, "u");
  const langues = Object.entries(REGLES.langues).map(([nom, src]) => [nom, new RegExp(src, "u")]);
  const RANG = { "débutant": 0, "intermédiaire": 1, "avancé": 2 };

  function profil(texte) {
    const n = simple(texte);
    const m = expDescription.exec(n);
    let annees = m ? parseFloat(m.slice(1).find((g) => g)) : null;
    if (annees === null && etudiant.test(n)) annees = 0;
    const niveau = annees === null ? "" : annees < 2 ? "débutant" : annees < 5 ? "intermédiaire" : "avancé";
    return {
      technos: technos.filter(([, re]) => re.test(texte)).map(([nom]) => nom),
      competences: competences.filter(([, re]) => re.test(n)).map(([nom]) => nom),
      annees, niveau,
      langues: langues.filter(([, re]) => re.test(n)).map(([nom]) => nom),
      chercheStage: stageRecherche.test(n),
    };
  }

  function comparer(p, o) {
    const t = o.technos, s = o.competences;
    if (!t.length && !s.length) return null;
    const communT = t.filter((x) => p.technos.includes(x));
    const communS = s.filter((x) => p.competences.includes(x));
    let gagne = 0, possible = 0;
    if (t.length) { gagne += 55 * (0.6 * communT.length / t.length + 0.4 * Math.min(communT.length, 4) / 4); possible += 55; }
    if (s.length) { gagne += 25 * communS.length / s.length; possible += 25; }
    possible += 20;
    let niveau;
    if (o.niveau in RANG && p.niveau in RANG) {
      const ecart = RANG[o.niveau] - RANG[p.niveau];
      if (ecart <= 0) { gagne += 20; niveau = "accessible"; }
      else if (ecart === 1) { gagne += 5; niveau = "un peu au-dessus"; }
      else niveau = "bien au-dessus";
    } else { gagne += 10; niveau = "non précisé"; }
    let note = 100 * gagne / possible;
    const elements = t.length + s.length;
    note *= 0.6 + 0.4 * Math.min(elements, 4) / 4;
    if (p.chercheStage && o.stage) note += 10;
    return {
      note: Math.min(100, pythonRound(note)),
      communs: communT, manquants: t.filter((x) => !p.technos.includes(x)),
      communsCompetences: communS, niveau, peuInfo: elements < 4,
    };
  }

  // round() de Python arrondit les .5 au nombre pair : on fait pareil pour avoir les mêmes notes.
  function pythonRound(x) {
    const bas = Math.floor(x), reste = x - bas;
    if (Math.abs(reste - 0.5) < 1e-9) return bas % 2 === 0 ? bas : bas + 1;
    return Math.round(x);
  }

  function classer(p, offres) {
    const resultats = [];
    let sansInfo = 0;
    for (const o of offres) {
      const r = comparer(p, o);
      if (r) resultats.push({ offre: o, ...r }); else sansInfo++;
    }
    // Même ordre que Python : note, nombre de technologies en commun, puis titre (comparé lettre par lettre).
    const titre = (a, b) => (a.offre.titreTri < b.offre.titreTri ? -1 : a.offre.titreTri > b.offre.titreTri ? 1 : 0);
    resultats.sort((a, b) => b.note - a.note || b.communs.length - a.communs.length || titre(a, b));
    return { resultats, sansInfo };
  }
  return { profil, comparer, classer, simple };
}
if (typeof module !== "undefined") module.exports = { creerComparateur };
// Lecture du texte d'un .docx dans le navigateur, sans bibliothèque.
// Un .docx est une archive ZIP : on cherche word/document.xml, on le décompresse, puis on lit les <w:t>.
async function texteDocx(octets) {
  const vue = new DataView(octets.buffer, octets.byteOffset, octets.byteLength);
  // Fin du répertoire central : signature 0x06054b50, cherchée en partant de la fin.
  let fin = -1;
  for (let i = octets.length - 22; i >= Math.max(0, octets.length - 65557); i--) {
    if (vue.getUint32(i, true) === 0x06054b50) { fin = i; break; }
  }
  if (fin < 0) throw new Error("Ce fichier n'est pas un document Word (.docx).");
  const nbEntrees = vue.getUint16(fin + 10, true);
  let pos = vue.getUint32(fin + 16, true);
  const decodeur = new TextDecoder("utf-8");
  for (let n = 0; n < nbEntrees; n++) {
    if (vue.getUint32(pos, true) !== 0x02014b50) break;
    const methode = vue.getUint16(pos + 10, true);
    const tailleCompressee = vue.getUint32(pos + 20, true);
    const longueurNom = vue.getUint16(pos + 28, true);
    const longueurExtra = vue.getUint16(pos + 30, true);
    const longueurCommentaire = vue.getUint16(pos + 32, true);
    const debutLocal = vue.getUint32(pos + 42, true);
    const nom = decodeur.decode(octets.subarray(pos + 46, pos + 46 + longueurNom));
    if (nom === "word/document.xml") {
      const debutDonnees = debutLocal + 30 + vue.getUint16(debutLocal + 26, true) + vue.getUint16(debutLocal + 28, true);
      const donnees = octets.subarray(debutDonnees, debutDonnees + tailleCompressee);
      let xml;
      if (methode === 0) xml = decodeur.decode(donnees);
      else if (methode === 8) {
        const flux = new Blob([donnees]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
        xml = await new Response(flux).text();
      } else throw new Error("Compression non prise en charge dans ce fichier Word.");
      return texteDepuisXml(xml);
    }
    pos += 46 + longueurNom + longueurExtra + longueurCommentaire;
  }
  throw new Error("Ce fichier Word ne contient pas de texte lisible.");
}

function texteDepuisXml(xml) {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const lignes = [];
  for (const p of doc.getElementsByTagNameNS(W, "p")) {
    let ligne = "";
    const parcourir = (noeud) => {
      for (const e of noeud.children) {
        if (e.namespaceURI === W && e.localName === "t") ligne += e.textContent;
        else if (e.namespaceURI === W && e.localName === "tab") ligne += " ";
        else if (e.namespaceURI === W && (e.localName === "br" || e.localName === "cr")) ligne += "\n";
        else if (!(e.namespaceURI === W && e.localName === "p")) parcourir(e);
      }
    };
    parcourir(p);
    lignes.push(ligne);
  }
  return lignes.join("\n");
}
