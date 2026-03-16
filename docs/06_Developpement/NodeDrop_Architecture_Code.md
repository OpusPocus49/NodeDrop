NodeDrop — Architecture du code
1. Objet du document

Ce document définit l’architecture du code de NodeDrop pour la version 1.

Il précise :

l’organisation des dossiers et fichiers Python,

les responsabilités de chaque module,

les classes principales à prévoir,

les relations entre les composants,

les règles de développement à respecter.

L’objectif est de disposer d’une base de code claire, maintenable et extensible.

2. Principes généraux de développement

Le code de NodeDrop doit respecter les principes suivants.

Séparation des responsabilités

Chaque fichier doit avoir une fonction précise.

Lisibilité

Les noms des fichiers, classes, méthodes et variables doivent être explicites.

Modularité

Les composants doivent pouvoir évoluer sans imposer une refonte complète du projet.

Extensibilité

L’architecture doit permettre l’ajout futur :

d’un mode distant,

d’une authentification renforcée,

d’une meilleure gestion des transferts.

Robustesse

Le code doit prévoir les erreurs courantes :

machine indisponible,

mot de passe invalide,

erreur réseau,

erreur disque.

3. Arborescence du code

Structure recommandée :

src
│
├── main.py
│
├── gui
│   ├── __init__.py
│   ├── main_window.py
│   ├── dialogs.py
│   ├── widgets.py
│   └── ui_helpers.py
│
├── network
│   ├── __init__.py
│   ├── discovery.py
│   ├── listener.py
│   ├── client.py
│   ├── protocol.py
│   └── session.py
│
├── core
│   ├── __init__.py
│   ├── app_manager.py
│   ├── peer_manager.py
│   ├── transfer_manager.py
│   ├── auth_manager.py
│   └── models.py
│
├── utils
│   ├── __init__.py
│   ├── file_utils.py
│   ├── hash_utils.py
│   ├── log_utils.py
│   └── config.py
4. Rôle de chaque dossier
4.1 src/

Contient tout le code source de l’application.

4.2 gui/

Contient tous les composants liés à l’interface graphique.

On y place :

la fenêtre principale,

les boîtes de dialogue,

les widgets personnalisés,

les utilitaires d’affichage.

4.3 network/

Contient tous les composants réseau.

On y place :

découverte LAN,

écoute TCP,

client TCP,

protocole de messages,

gestion de session réseau.

4.4 core/

Contient la logique métier centrale.

On y place :

gestion globale de l’application,

gestion des pairs,

authentification,

transferts,

modèles de données.

4.5 utils/

Contient les fonctions transverses réutilisables.

On y place :

gestion fichiers,

logs,

hash,

configuration.

5. Description détaillée des fichiers
5.1 main.py
Rôle

Point d’entrée principal de l’application.

Responsabilités

initialiser l’application Qt,

charger la configuration,

initialiser le système de logs,

créer le gestionnaire principal,

ouvrir la fenêtre principale,

démarrer la boucle de l’interface.

Ce que main.py ne doit pas faire

contenir la logique métier,

gérer les transferts,

gérer directement le réseau.

5.2 gui/main_window.py
Rôle

Contient la fenêtre principale de NodeDrop.

Responsabilités

afficher la liste des machines détectées,

afficher les détails de la machine sélectionnée,

contenir les boutons d’action,

afficher le journal d’activité,

transmettre les actions utilisateur à AppManager.

Classe principale

MainWindow

5.3 gui/dialogs.py
Rôle

Contient les boîtes de dialogue secondaires.

Responsabilités

dialogue de réception de transfert,

dialogue de progression,

dialogue d’erreur,

confirmation de fermeture.

Classes possibles

IncomingTransferDialog

TransferProgressDialog

ErrorDialog

ConfirmExitDialog

5.4 gui/widgets.py
Rôle

Contient les composants visuels réutilisables.

Exemples

widget de ligne pour un pair,

widget de progression,

widget de journal.

Classes possibles

PeerListItemWidget

ProgressWidget

LogPanelWidget

5.5 gui/ui_helpers.py
Rôle

Contient des fonctions utilitaires pour l’interface.

Exemples

formatage de tailles,

formatage du temps restant,

conversion d’états en libellés visuels.

5.6 network/discovery.py
Rôle

Gère la découverte réseau sur le LAN via UDP.

Responsabilités

envoyer périodiquement les messages d’annonce,

écouter les annonces des autres machines,

remonter les informations au PeerManager.

Classes possibles

DiscoveryService

DiscoveryBroadcaster

DiscoveryListener

5.7 network/listener.py
Rôle

Gère l’écoute TCP pour les connexions entrantes.

Responsabilités

ouvrir le port TCP,

accepter les connexions,

transmettre les connexions reçues au gestionnaire de session.

Classe principale

TcpListener

5.8 network/client.py
Rôle

Gère l’ouverture des connexions sortantes.

Responsabilités

se connecter à une machine distante,

envoyer les premiers messages de session,

exposer une interface claire pour AppManager.

Classe principale

TcpClient

5.9 network/protocol.py
Rôle

Centralise la définition du protocole NodeDrop.

Responsabilités

définir les types de messages,

encoder les messages en JSON,

décoder les messages reçus,

valider la structure minimale des messages.

Contenu possible

constantes de messages,

fonctions encode_message(),

fonctions decode_message().

5.10 network/session.py
Rôle

Représente et gère une session réseau active.

Responsabilités

suivre l’état de la session,

stocker les informations d’authentification,

envoyer et recevoir les messages d’une session,

notifier le TransferManager.

Classe principale

Session

5.11 core/app_manager.py
Rôle

Composant central de coordination de l’application.

Responsabilités

initialiser les services,

servir de passerelle entre GUI, réseau et logique métier,

réagir aux actions utilisateur,

piloter les connexions,

piloter les transferts,

transmettre les événements à l’interface.

Classe principale

AppManager

Position dans le projet

C’est le chef d’orchestre de NodeDrop V1.

5.12 core/peer_manager.py
Rôle

Gère la liste des machines détectées.

Responsabilités

enregistrer ou mettre à jour les pairs,

supprimer les pairs expirés,

fournir les pairs disponibles à l’interface,

suivre leur statut.

Classe principale

PeerManager

5.13 core/transfer_manager.py
Rôle

Gère la préparation, l’exécution et le suivi des transferts.

Responsabilités

préparer la liste des fichiers,

calculer la taille totale,

envoyer les métadonnées,

envoyer les blocs,

recevoir les blocs,

mettre à jour la progression.

Classe principale

TransferManager

5.14 core/auth_manager.py
Rôle

Gère l’authentification entre deux machines.

Responsabilités

vérifier le mot de passe,

signaler succès ou échec,

fournir une interface isolée pour les futures évolutions de sécurité.

Classe principale

AuthManager

5.15 core/models.py
Rôle

Contient les modèles de données internes.

Modèles possibles

Peer

TransferJob

TransferFile

SessionState

Intérêt

Éviter de disperser les structures de données dans tous les fichiers.

5.16 utils/file_utils.py
Rôle

Contient les fonctions de manipulation des fichiers et dossiers.

Responsabilités

parcourir récursivement un dossier,

construire les chemins relatifs,

calculer la taille totale,

préparer les dossiers de destination.

5.17 utils/hash_utils.py
Rôle

Contient les fonctions de calcul d’empreintes.

Utilité

Même si la V1 n’exploite pas encore tout, ce module prépare :

vérification d’intégrité,

évolutions futures.

Fonctions possibles

compute_sha256(path)

5.18 utils/log_utils.py
Rôle

Gère la journalisation de l’application.

Responsabilités

initialiser le système de logs,

écrire les événements dans un fichier,

éventuellement fournir un flux pour la GUI.

Fonctions possibles

setup_logging()

get_logger()

5.19 utils/config.py
Rôle

Contient la configuration centrale de l’application.

Exemples

ports réseau,

fréquence des annonces UDP,

taille des blocs,

chemins par défaut,

constantes globales.

6. Modèles de données principaux
6.1 Peer

Représente une machine détectée.

Attributs recommandés

node_id

node_name

ip

port

status

last_seen

6.1.1 NodeIdentity

Représente l’identité de l’instance NodeDrop locale.

Contrairement au modèle Peer qui représente une machine distante détectée sur le réseau, NodeIdentity représente la machine exécutant l’application.

Attributs recommandés

node_id
identifiant unique généré pour l’instance NodeDrop

node_name
nom de la machine locale

listen_port
port TCP utilisé par le service NodeDrop

status
état actuel de la machine (available, busy)

Objectif

Centraliser les informations d’identité de l’application afin d’éviter leur duplication dans les modules réseau.

Cette identité est utilisée pour :

les annonces UDP de découverte
les messages de session
les logs
les futures extensions (mode distant, authentification avancée).

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

6.3 TransferFile

Représente un fichier à envoyer ou recevoir.

Attributs recommandés

name

full_path

relative_path

size

6.4 TransferJob

Représente un transfert global.

Attributs recommandés

job_id

session_id

files

total_size

transferred_size

status

started_at

finished_at

7. Relations entre les composants

Le flux logique principal sera le suivant :

Démarrage

main.py initialise l’application

AppManager démarre les services

DiscoveryService et TcpListener sont lancés

Détection

DiscoveryService reçoit une annonce

PeerManager met à jour la liste

MainWindow affiche la liste actualisée

Connexion

l’utilisateur clique sur un pair

MainWindow transmet à AppManager

AppManager utilise TcpClient

une Session est créée

Authentification

Session échange les messages

AuthManager valide le mot de passe

Transfert

TransferManager prépare les fichiers

file_utils.py calcule la structure

Session transmet les messages et blocs

l’interface reçoit les mises à jour

8. Communication entre GUI et logique métier

Il faut éviter que l’interface appelle directement le réseau.

La communication doit suivre cette logique :

GUI -> AppManager -> Core / Network
Core / Network -> AppManager -> GUI

C’est un point important.
Sinon le code devient rapidement difficile à maintenir.

9. Stratégie de concurrence

L’interface Qt ne doit pas être bloquée par les opérations réseau.

Il faut donc séparer :

le thread GUI,

les traitements réseau,

les transferts longs.

Pour la V1, deux approches sont possibles :

Option 1

threading

Option 2

QThread

Mon avis :
pour une application PySide6, QThread est plus cohérent côté interface, mais threading peut être plus simple pour démarrer.

Pour la V1, on peut partir sur une architecture pragmatique :

interface dans le thread principal,

découverte et écoute réseau dans des threads dédiés,

transfert dans un thread dédié.

10. Règles de codage

Le projet devra suivre quelques règles simples.

Style

noms explicites,

méthodes courtes,

commentaires utiles seulement quand nécessaire,

pas de logique métier dans l’interface.

Organisation

une classe principale par responsabilité forte,

pas de duplication inutile,

constantes centralisées dans config.py.

Qualité

journaliser les erreurs importantes,

capturer les exceptions réseau critiques,

éviter les fonctions trop longues.

11. Ordre recommandé d’implémentation

Pour éviter le désordre, le développement doit suivre cet ordre.

Étape 1

Mettre en place la structure du projet et les utilitaires de base :

config.py

log_utils.py

models.py

Étape 2

Créer la fenêtre principale minimale :

MainWindow

liste vide des pairs

journal

Étape 3

Implémenter la découverte LAN :

discovery.py

peer_manager.py

Étape 4

Implémenter l’écoute TCP :

listener.py

client.py

session.py

Étape 5

Implémenter le protocole :

protocol.py

Étape 6

Implémenter l’authentification :

auth_manager.py

Étape 7

Implémenter le moteur de transfert :

transfer_manager.py

file_utils.py

Étape 8

Créer les dialogues :

réception

progression

erreurs

Étape 9

Tester sur deux machines réelles

Étape 10

Préparer le packaging de l’application

12. Évolutions futures prévues dans le code

L’architecture actuelle doit permettre l’ajout futur de :

remote_discovery.py

remote_transport.py

crypto_utils.py

history_manager.py

sync_manager.py

Cela justifie le découpage modulaire posé dès la V1.

13. Résumé

L’architecture du code de NodeDrop V1 repose sur :

une interface Qt dédiée à l’expérience utilisateur,

une logique métier centralisée dans core,

un réseau isolé dans network,

des utilitaires réutilisables dans utils,

un pilotage global assuré par AppManager.

Cette structure permet :

un développement progressif,

une maintenance claire,

une bonne base pour les évolutions futures.