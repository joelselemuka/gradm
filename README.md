# Gestion de supermarché

Application Django server-rendered pour la gestion du catalogue, des stocks par lots, des ventes et des caisses. Elle privilégie les services métier transactionnels et les permissions côté serveur.

## Démarrage local

1. Créer un environnement virtuel et installer `pip install -r requirements/base.txt`.
2. Copier `.env.example` vers `.env` et renseigner les secrets nécessaires.
3. En développement sans PostgreSQL, Django utilise SQLite. En environnement Docker, renseigner `POSTGRES_*`.
4. Exécuter `python manage.py migrate`, puis `python manage.py createsuperuser`.
5. Lancer `python manage.py runserver`.

## Docker

Copier `.env.example` vers `.env`, changer les secrets, puis exécuter `docker compose up --build`. Les services démarrés sont `web`, PostgreSQL, Redis, Celery worker et Celery Beat.

## Principes métier déjà implémentés

- rôles ADMIN, GÉRANT et CAISSIER, contrôlés dans les services ;
- produits, variantes, SKU et code-barres uniques ;
- lots, mouvements de stock et réception atomique ;
- allocation FEFO, avec interdiction de vendre un lot expiré ;
- vente atomique, paiement espèces/carte/mobile money/autre ;
- facture immuable par statut et annulation réservée à ADMIN ;
- mouvement de restauration et audit lors de l’annulation.

## Trésorerie et caisse

Une session de caisse ouverte est obligatoire pour valider une vente. Chaque facture est automatiquement rattachée à cette session, et seules les ventes réglées en espèces alimentent le solde physique de la caisse.

L'ADMIN peut ouvrir une caisse pour un caissier avec son fonds initial, enregistrer les apports, achats, dépenses, retraits et opérations de change. Toutes ces lignes sont conservées dans un livre de caisse : une correction annule une écriture sans la supprimer. La clôture calcule le montant théorique, compare le comptage réel, garde l'écart et utilise le montant réel compté comme report physique du lendemain. Les paiements carte et mobile money restent dans le chiffre d'affaires mais ne sont jamais assimilés à du cash physique.

## Sauvegarde PostgreSQL

Planifier `pg_dump` au moins quotidiennement, chiffrer et conserver les sauvegardes hors de l’hôte de production. Pour restaurer, créer une base vide puis exécuter `pg_restore --clean --if-exists -d <database> <backup>`. Tester régulièrement la restauration sur un environnement isolé.
