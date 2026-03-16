NodeDrop — Architecture générale
1. Objet du document

Ce document décrit l’architecture générale de NodeDrop pour la version 1.

Il a pour objectif de définir :

les grands composants du logiciel,

leurs responsabilités,

leurs interactions,

la logique de communication interne,

les principes de conception à respecter.

L’architecture doit permettre de développer une première version fonctionnelle sur réseau local, tout en préparant l’évolution future vers un mode distant.

2. Principes de conception

L’architecture de NodeDrop repose sur plusieurs principes fondamentaux.

2.1 Séparation des responsabilités

Chaque composant doit avoir un rôle précis.

Exemples :

l’interface ne gère pas directement les sockets réseau,

le moteur de transfert ne gère pas l’affichage,

la découverte réseau ne gère pas les fichiers.

Cette séparation facilite :

la maintenance,

les tests,

l’évolution du logiciel.

2.2 Modularité

Le projet doit être organisé en modules indépendants et cohérents.

Cela permettra :

de remplacer un composant sans réécrire tout le programme,

d’ajouter plus tard un mode distant,

d’isoler plus facilement les erreurs.

2.3 Extensibilité

La version 1 fonctionne uniquement sur LAN, mais l’architecture ne doit pas dépendre exclusivement de cette contrainte.

Le logiciel doit être conçu autour d’une notion générique de :

pair,

session,

transfert,

backend réseau.

Ainsi, un futur backend distant pourra être ajouté sans refondre toute l’application.

2.4 Robustesse

Le logiciel doit être capable de :

gérer des erreurs réseau,

supporter de gros transferts,

éviter les blocages de l’interface,

conserver un état cohérent.

3. Vue d’ensemble de l’architecture

NodeDrop peut être vu comme un ensemble de couches fonctionnelles.

Couche 1 — Interface utilisateur

Affichage des machines, des demandes de connexion, des transferts et des messages.

Couche 2 — Contrôle applicatif

Coordination entre l’interface, le réseau, l’authentification et le moteur de transfert.

Couche 3 — Services métier

Gestion des pairs, des sessions, des transferts, des fichiers et des logs.

Couche 4 — Réseau

Découverte LAN, écoute réseau, connexions TCP, échanges de messages.

4. Composants principaux
4.1 Interface graphique
Rôle

L’interface graphique permet à l’utilisateur de :

voir les machines détectées,

lancer une demande de connexion,

accepter ou refuser une demande,

choisir des fichiers ou dossiers,

suivre l’état d’un transfert.

Responsabilités

affichage de la liste des pairs,

affichage des états,

interaction utilisateur,

affichage des journaux et messages,

affichage des barres de progression.

Ce que l’interface ne doit pas faire

ouvrir directement des sockets,

implémenter la logique réseau,

gérer directement l’écriture des fichiers transférés.

L’interface doit déléguer ces tâches aux modules applicatifs.

4.2 Gestionnaire d’application
Rôle

Le gestionnaire d’application coordonne le comportement global du logiciel.

Il agit comme une couche centrale entre :

l’interface,

les services réseau,

le moteur de transfert,

les logs.

Responsabilités

initialiser les composants,

démarrer les services réseau,

recevoir les événements système,

transmettre les actions utilisateur aux modules concernés,

mettre à jour l’interface selon l’état réel du logiciel.

Exemple

Si un utilisateur clique sur une machine puis sur “Se connecter”, le gestionnaire d’application :

récupère la machine ciblée,

demande au module réseau d’ouvrir une session,

attend la réponse,

informe l’interface du résultat.

4.3 Gestion des pairs
Rôle

Le module de gestion des pairs maintient la liste des machines détectées.

Responsabilités

enregistrer les pairs visibles,

mettre à jour leur statut,

supprimer les pairs expirés,

fournir à l’interface une liste exploitable.

Données gérées

Pour chaque pair :

identifiant temporaire,

nom de machine,

adresse IP,

port de service,

statut,

dernière présence connue.

Remarque

Ce module ne doit pas savoir si un pair a été découvert par LAN ou, plus tard, par Internet. Il doit manipuler une représentation abstraite d’un pair.

4.4 Découverte réseau
Rôle

Le module de découverte réseau permet aux instances NodeDrop de s’annoncer mutuellement sur le réseau local.

Principe

Chaque instance :

diffuse périodiquement un message de présence,

écoute les messages diffusés par les autres instances.

Responsabilités

envoyer des annonces de présence,

écouter les annonces,

transmettre les informations au gestionnaire de pairs.

Technologie prévue

UDP broadcast sur le réseau local.

Justification

Le broadcast UDP est simple, léger, et adapté à un environnement LAN.

4.5 Gestion des connexions
Rôle

Ce module établit et gère les connexions entre deux machines.

Responsabilités

écouter les demandes de connexion entrantes,

initier une connexion vers une machine distante,

transmettre les demandes à l’utilisateur distant,

gérer acceptation ou refus,

ouvrir une session de communication.

Technologie prévue

TCP pour les communications fiables.

Pourquoi TCP

Le transfert de fichiers exige :

ordre correct des données,

fiabilité,

contrôle d’erreurs au niveau transport.

4.6 Gestion des sessions
Rôle

Le module de session représente une connexion active entre deux machines.

Responsabilités

stocker l’état de la session,

suivre si la session est :

en attente,

acceptée,

refusée,

authentifiée,

fermée,

transmettre les événements au moteur de transfert.

Intérêt

Cela évite de mélanger :

la connexion réseau brute,

la logique fonctionnelle de la communication.

4.7 Authentification
Rôle

Le module d’authentification valide qu’une connexion est autorisée.

Responsabilités

gérer la vérification du mot de passe,

refuser les connexions non valides,

fournir un état d’authentification à la session.

Limites V1

Dans la V1, l’authentification reste simple, mais elle doit être isolée dans un module dédié afin d’être renforcée plus tard.

Évolution future

Ce module pourra évoluer vers :

dérivation de clé,

challenge-réponse,

chiffrement de session,

comptes utilisateurs.

4.8 Moteur de transfert
Rôle

Le moteur de transfert gère l’envoi et la réception des fichiers.

Responsabilités

préparer le transfert,

calculer les métadonnées,

envoyer les fichiers par blocs,

reconstruire les fichiers côté réception,

remonter les informations de progression,

détecter les erreurs de transfert.

Contraintes

Il doit :

limiter l’usage mémoire,

supporter de gros fichiers,

fonctionner sur un ou plusieurs fichiers,

gérer les dossiers complets.

4.9 Gestion des fichiers
Rôle

Ce module manipule les chemins, fichiers et dossiers à transférer.

Responsabilités

parcourir un dossier récursivement,

lister les fichiers,

calculer la taille totale,

générer les chemins relatifs,

préparer les dossiers de destination.

Intérêt

La logique système de fichiers doit être séparée de la logique réseau.

4.10 Journalisation
Rôle

Le module de journalisation enregistre les événements du logiciel.

Responsabilités

enregistrer les démarrages,

enregistrer les détections de pairs,

enregistrer les connexions,

enregistrer les transferts,

enregistrer les erreurs.

Objectif

Permettre :

le diagnostic,

le débogage,

le suivi de l’usage.

5. Modèle de communication interne

L’application fonctionne selon une logique événementielle.

Exemple de séquence

l’application démarre,

le service de découverte LAN s’active,

des pairs sont détectés,

le gestionnaire de pairs met à jour la liste,

l’interface affiche les pairs,

l’utilisateur sélectionne un pair,

le gestionnaire d’application demande l’ouverture d’une connexion,

le pair distant reçoit la demande,

l’utilisateur distant accepte ou refuse,

la session s’ouvre,

l’utilisateur choisit les fichiers,

le moteur de transfert démarre,

la progression est remontée à l’interface,

le transfert se termine,

le journal enregistre l’opération.

6. Architecture logique des flux

NodeDrop repose sur deux grands flux réseau.

6.1 Flux de découverte

Utilisé pour annoncer la présence des machines.

Caractéristiques :

léger,

périodique,

non critique,

basé sur UDP.

Contenu typique :

nom de machine,

identifiant NodeDrop,

adresse IP,

port d’écoute,

statut.

6.2 SessionState

Représente l’état d’une session de communication entre deux machines.

États possibles

PENDING
La demande de session vient d’être envoyée ou reçue.

REQUESTED
La session a été demandée et attend une réponse de l’utilisateur distant.

ACCEPTED
La connexion TCP est établie et acceptée.

REJECTED
La demande de session a été refusée.

AUTHENTICATING
La phase d’authentification est en cours.

AUTHENTICATED
La session est validée et prête à transférer des fichiers.

TRANSFERRING
Un transfert de fichiers est en cours.

CLOSED
La session est terminée normalement.

ERROR
Une erreur est survenue pendant la session.

7. Structure logique du projet

Organisation cible du code :

src
│
├── main.py
│
├── gui
│   ├── main_window.py
│   ├── dialogs.py
│   └── widgets.py
│
├── network
│   ├── discovery.py
│   ├── listener.py
│   ├── client.py
│   ├── protocol.py
│   └── session.py
│
├── core
│   ├── app_manager.py
│   ├── peer_manager.py
│   ├── transfer_manager.py
│   ├── auth_manager.py
│   └── models.py
│
├── utils
    ├── config.py
    ├── file_utils.py
    ├── log_utils.py
    └── hash_utils.py
8. Modèles logiques principaux

8.1 NodeIdentity

Représente l’identité de l’instance NodeDrop locale.

Attributs possibles :

node_id
node_name
port
status

8.2 Peer

Représente une machine visible sur le réseau.

Attributs possibles :

identifiant
nom
adresse IP
port
statut
dernière activité

8.3 Session

Représente une connexion active ou en attente entre deux machines.

Attributs possibles :

identifiant de session
pair local
pair distant
état
authentifié ou non
heure de création

8.4 TransferJob

Représente un transfert en cours ou terminé.

Attributs possibles :

identifiant
session associée
liste des fichiers
taille totale
taille transférée
état
progression

9. Contraintes d’implémentation
9.1 Interface non bloquante

Les opérations réseau et les transferts ne doivent pas figer l’interface graphique.

Conséquence :

les traitements réseau devront être isolés du thread GUI.

9.2 Gestion par blocs

Les fichiers devront être lus et transmis par blocs, et non chargés intégralement en mémoire.

9.3 Gestion d’erreurs

L’application devra prévoir :

machine indisponible,

connexion refusée,

mot de passe invalide,

coupure réseau,

erreur d’écriture disque.

9.4 Traçabilité

Les événements importants devront être journalisés.

10. Préparation de l’évolution future

Même si la V1 est locale, l’architecture doit préparer un futur mode distant.

Pour cela, il faudra éviter de coupler fortement :

la découverte LAN,

la logique de session,

le moteur de transfert.

L’idée est de pouvoir, plus tard, remplacer ou compléter :

LanDiscoveryService
par

RemoteDiscoveryService

et

LanTransport
par

RemoteTransport

sans réécrire :

l’interface,

la gestion des sessions,

le moteur de transfert.

11. Résumé architectural

NodeDrop V1 sera construit autour de cinq axes principaux :

1. Interface graphique

Affichage et interactions utilisateur.

2. Découverte et gestion des pairs

Détection LAN et maintien de la liste des machines.

3. Connexions et sessions

Établissement des communications entre machines.

4. Moteur de transfert

Envoi et réception des fichiers par blocs.

5. Services transverses

Authentification, gestion des fichiers, journalisation.

Cette architecture permet une V1 locale propre, modulaire et extensible.