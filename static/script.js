/* Formulaire en étapes avec validation.
   Tout reste dans un seul <form> : les étapes non actives sont masquées,
   donc l'envoi contient toujours l'intégralité des champs.
   Sans JavaScript, toutes les étapes restent visibles (dégradation gracieuse). */
(function () {
  var form = document.getElementById('formulaire');
  if (!form) return;

  var etapes = Array.prototype.slice.call(form.querySelectorAll('.etape'));
  if (etapes.length < 2) return;

  var nav = form.querySelector('.etapes-nav');
  var puces = Array.prototype.slice.call(form.querySelectorAll('.etape-puce'));
  var barre = form.querySelector('.progression-barre');
  var btnPrec = document.getElementById('btn-precedent');
  var btnSuiv = document.getElementById('btn-suivant');
  var btnAnalyser = document.getElementById('btn-analyser');
  var zoneErreur = document.getElementById('message-erreur');

  var courant = 0;

  document.body.classList.add('js-etapes');
  if (nav) nav.hidden = false;
  btnPrec.hidden = false;
  btnSuiv.hidden = false;

  function afficherErreur(texte) {
    if (!zoneErreur) return;
    if (texte) { zoneErreur.textContent = texte; zoneErreur.hidden = false; }
    else { zoneErreur.textContent = ''; zoneErreur.hidden = true; }
  }

  /* Une étape est valide si :
     - tous ses champs obligatoires sont remplis et dans les bornes,
     - et, pour l'étape des symptômes, au moins une case est cochée. */
  function validerEtape(index) {
    var etape = etapes[index];
    var champs = Array.prototype.slice.call(etape.querySelectorAll('input, select'));

    var cases = champs.filter(function (c) { return c.type === 'checkbox'; });
    if (cases.length && !cases.some(function (c) { return c.checked; })) {
      afficherErreur('Cochez au moins un symptôme observé pour continuer.');
      cases[0].focus();
      return false;
    }

    for (var i = 0; i < champs.length; i++) {
      var c = champs[i];
      if (c.type === 'checkbox') continue;
      if (!c.checkValidity()) {
        afficherErreur('Veuillez remplir correctement le champ « ' + c.name +' ».');
        c.reportValidity();
        c.focus();
        return false;
      }
    }

    afficherErreur(null);
    return true;
  }

  function afficher(index, donnerFocus) {
    courant = Math.max(0, Math.min(index, etapes.length - 1));

    etapes.forEach(function (et, i) {
      var actif = i === courant;
      et.classList.toggle('active', actif);
      et.setAttribute('aria-hidden', actif ? 'false' : 'true');
    });

    puces.forEach(function (p, i) {
      p.classList.toggle('active', i === courant);
      p.classList.toggle('faite', i < courant);
      if (i === courant) { p.setAttribute('aria-current', 'step'); }
      else { p.removeAttribute('aria-current'); }
    });

    if (barre) barre.style.width = ((courant + 1) / etapes.length * 100) + '%';

    btnPrec.disabled = (courant === 0);
    var derniere = (courant === etapes.length - 1);
    btnSuiv.hidden = derniere;
    btnAnalyser.hidden = !derniere;

    if (donnerFocus) {
      var legende = etapes[courant].querySelector('legend');
      if (legende) {
        legende.setAttribute('tabindex', '-1');
        legende.focus({ preventScroll: true });
      }
      etapes[courant].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  btnSuiv.addEventListener('click', function () {
    if (validerEtape(courant)) afficher(courant + 1, true);
  });

  // Revenir en arrière est toujours autorisé
  btnPrec.addEventListener('click', function () {
    afficherErreur(null);
    afficher(courant - 1, true);
  });

  function allerVers(cible) {
    if (cible > courant && !validerEtape(courant)) return;
    afficher(cible, true);
  }

  puces.forEach(function (p) {
    p.setAttribute('role', 'button');
    p.setAttribute('tabindex', '0');
    p.addEventListener('click', function () {
      allerVers(parseInt(p.getAttribute('data-cible'), 10));
    });
    p.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        allerVers(parseInt(p.getAttribute('data-cible'), 10));
      }
    });
  });

  // Entrée : passer à l'étape suivante plutôt que d'envoyer le formulaire
  form.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && courant < etapes.length - 1) {
      e.preventDefault();
      if (validerEtape(courant)) afficher(courant + 1, true);
    }
  });

  // À l'envoi : on vérifie toutes les étapes et on ramène l'utilisateur
  // sur la première qui pose problème (sinon un champ masqué bloquerait sans explication)
  form.addEventListener('submit', function (e) {
    for (var i = 0; i < etapes.length; i++) {
      var etaitCourant = courant;
      courant = i;
      var ok = validerEtape(i);
      courant = etaitCourant;
      if (!ok) {
        e.preventDefault();
        afficher(i, true);
        validerEtape(i);
        return;
      }
    }
    afficherErreur(null);
  });

  afficher(0, false);
})();
