ROADMAP V2

NodeDrop — Roadmap corrigée et mise à jour
1. Objet du document

Ce document définit la feuille de route opérationnelle de développement de NodeDrop.

Il précise :

les phases du projet

les objectifs techniques

les livrables attendus

les critères de validation

l’état d’avancement réel

Cette version est corrigée pour refléter la progression déjà obtenue sur le projet.

2. Vision globale du projet

NodeDrop est développé de manière progressive, en respectant une architecture modulaire claire :

Base applicative

Découverte LAN

Sessions TCP

Authentification

Transfert de fichiers
sation

Packaging V1

L’objectif de la V1 reste inchangé :

permettre le transfert local de fichiers et dossiers entre machines NodeDrop présentes sur le même réseau.

3. État actuel synthétique
Phases validées

Phase 0 — Initialisation du projet ✅

Phase 1 — Fondations techniques ✅

Phase 2A — Découverte LAN + sessions TCP de base ✅

Phase 2B — Intégration Core (PeerManager + AppManager) ✅

Phase 2C / 3 — Authentification minimale TCP ✅

État technique validé

Les éléments suivants sont désormais fonctionnels et testés :

src/utils/config.py

src/utils/log_utils.py

src/core/models.py

src/core/peer_manager.py

src/core/auth_manager.py

src/core/app_manager.py

src/network/protocol.py

src/network/discovery.py

src/network/listener.py

src/network/session.py

Validation globale actuelle

33 tests passent

découverte LAN validée

session TCP validée

authentification TCP validée

intégration Core validée

4. Phase 0 — Initialisation du projet ✅ VALIDÉE
Objectif

Préparer l’environnement de développement et la structure du projet.

Tâches

créer l’arborescence du projet

créer les dossiers principaux

préparer les fichiers de base

rédiger la documentation initiale

définir l’architecture générale

Résultat attendu

Le projet possède :

une structure claire

une documentation de référence

une base saine pour le développement

Statut

Validée

5. Phase 1 — Fondations techniques ✅ VALIDÉE
Objectif

Mettre en place le socle technique minimal de NodeDrop.

Tâches

implémenter config.py

implémenter log_utils.py

implémenter models.py

définir les constantes de fonctionnement

définir les modèles métier centraux

Résultat attendu

Le projet possède :

une configuration centralisée

un système de logs fonctionnel

des modèles métier unifiés

Statut

Validée

6. Phase 2A — Réseau de base : découverte LAN + session TCP ✅ VALIDÉE
Objectif

Permettre aux machines NodeDrop de :

se détecter sur le réseau local

initier une session TCP simple

Tâches
Découverte LAN

implémenter DiscoveryService

implémenter l’envoi UDP broadcast

implémenter l’écoute UDP

valider la détection locale

valider la détection croisée entre deux instances

Session TCP de base

implémenter SessionListener

conserver SessionClient dans session.py

implémenter SESSION_REQUEST

implémenter SESSION_ACCEPTED

implémenter SESSION_REJECTED

valider un test local loopback

Résultat attendu

Deux machines NodeDrop peuvent :

se détecter automatiquement

établir une première session TCP simple

Statut

Validée

7. Phase 2B — Intégration Core (PeerManager + AppManager) ✅ VALIDÉE
Objectif

Connecter proprement la couche réseau à la couche métier, sans coupler la GUI au réseau.

Tâches

finaliser PeerManager

implémenter un AppManager minimal

connecter DiscoveryService -> AppManager -> PeerManager

préparer la future remontée vers la GUI

gérer la déduplication métier des annonces réseau répétées

Résultat attendu

Le système sait :

enregistrer et mettre à jour les pairs découverts

exposer une liste de pairs propre à la couche supérieure

centraliser l’orchestration dans AppManager

Statut

Validée

8. Phase 2C / 3 — Authentification TCP minimale ✅ VALIDÉE
Objectif

Ajouter un verrou d’authentification après l’établissement de session TCP.

Tâches

implémenter AuthManager

corriger le protocole AUTH_*

étendre SessionListener

étendre SessionClient

intégrer l’authentification à AppManager

valider le handshake :

SESSION_REQUEST
SESSION_ACCEPTED
AUTH_REQUEST
AUTH_RESPONSE
AUTH_SUCCESS / AUTH_FAILED
Résultat attendu

Une session NodeDrop n’est considérée valide que si l’authentification réussit.

Statut

Validée

9. Phase 4 — Transfert simple de fichiers 🔜 PROCHAINE PHASE
Objectif

Permettre l’envoi réel d’un fichier simple entre deux machines.

Priorité

Phase suivante immédiate

Tâches

implémenter src/core/transfer_manager.py

définir la préparation d’un transfert simple

envoyer les métadonnées du fichier

envoyer les données du fichier

écrire le fichier côté réception

vérifier l’intégrité minimale

gérer les erreurs de base

ajouter les premiers tests d’intégration transfert

Périmètre V1 minimal

Pour rester sobre, cette phase doit d’abord supporter :

un seul fichier

un seul transfert

pas encore de dossier complet

pas encore de transfert multiple

pas encore d’UX avancée

Résultat attendu

Deux machines peuvent :

envoyer un fichier

le recevoir correctement

confirmer la réussite du transfert

Statut

À faire

10. Phase 5 — Transfert avancé
Objectif

Étendre le moteur de transfert après validation du transfert simple.

Tâches

support de plusieurs fichiers

support des dossiers

gestion des chemins relatifs

meilleure progression

meilleure gestion d’erreurs

reprise éventuelle plus tard si nécessaire

Résultat attendu

Le système supporte :

plusieurs fichiers

dossiers complets

opérations plus robustes

Statut

À faire

11. Phase 6 — Intégration GUI progressive
Objectif

Brancher proprement le moteur Core/Réseau à l’interface, sans casser l’architecture.

Tâches

connecter AppManager à la GUI

afficher les pairs découverts

permettre le lancement d’une session depuis l’interface

permettre la saisie / utilisation du mot de passe

afficher l’état de la connexion

afficher l’état du transfert

Résultat attendu

L’utilisateur peut piloter NodeDrop depuis l’interface, sans interaction directe avec les modules réseau.

Statut

À faire

12. Phase 7 — Interface utilisateur complète
Objectif

Finaliser l’expérience utilisateur pour la V1.

Tâches

fenêtre principale enrichie

liste des machines détectées

demande / réception de transfert

barre de progression

statut de session

messages d’erreur clairs

état de réussite / échec

Résultat attendu

L’interface devient exploitable en usage réel.

Statut

À faire

13. Phase 8 — Tests réels multi-machines
Objectif

Valider NodeDrop dans des conditions réelles.

Tâches

tests sur réseau local réel

tests sur Wi-Fi

tests sur Ethernet

tests entre plusieurs machines

tests sur fichiers petits / moyens / volumineux

validation de la stabilité

validation de l’intégrité des fichiers reçus

Résultat attendu

Le logiciel fonctionne correctement hors environnement purement local de test.

Statut

À faire

14. Phase 9 — Optimisation
Objectif

Améliorer les performances, la stabilité et la propreté technique.

Tâches

optimiser les transferts

améliorer la gestion mémoire

améliorer la gestion des threads

améliorer la robustesse réseau

harmoniser les logs

corriger les warnings et dépréciations

nettoyer le code

Résultat attendu

Le logiciel est plus stable, plus propre et plus performant.

Statut

À faire

15. Phase 10 — Packaging
Objectif

Distribuer NodeDrop comme application portable.

Tâches

préparer PyInstaller

produire l’exécutable

tester le lancement sur plusieurs machines

valider le fonctionnement sans installation

Résultat attendu

NodeDrop peut être exécuté comme application portable.

Statut

À faire

16. Phase 11 — Stabilisation V1
Objectif

Finaliser la première version publiable.

Tâches

correction des bugs restants

amélioration UX

nettoyage final du code

validation globale

gel du périmètre V1

Résultat attendu

Version 1 stable, cohérente, testée et diffusable.

Statut

À faire

17. V2 — Évolutions futures
Fonctionnalités envisagées

transfert distant

chiffrement renforcé

comptes utilisateurs

historique des transferts

synchronisation de dossiers

amélioration des performances

reprise de transfert

meilleure gestion de sécurité

Statut

Hors périmètre V1

18. Jalons mis à jour
Jalon	Objectif	Statut
J1	Fondations techniques	✅ Validé
J2	Découverte LAN	✅ Validé
J3	Session TCP	✅ Validé
J4	Authentification	✅ Validé
J5	Transfert simple	⏳ À faire
J6	Transfert avancé	⏳ À faire
J7	Intégration GUI	⏳ À faire
J8	Tests réels	⏳ À faire
J9	Optimisation	⏳ À faire
J10	Release V1	⏳ À faire
19. Critères actuels de réussite de la V1

La V1 sera considérée comme validée si :

deux machines se détectent automatiquement

une session TCP peut être établie

l’authentification fonctionne

un transfert de fichier fonctionne

les fichiers reçus sont corrects

l’interface est stable

le packaging portable est utilisable

20. Prochaine étape officielle
Prochaine phase à lancer

Phase 4 — Transfert simple de fichiers

Fichiers à préparer maintenant

src/core/transfer_manager.py

src/utils/file_utils.py

src/utils/hash_utils.py

Objectif immédiat

Construire un moteur minimal de transfert réel, avant toute montée en complexité côté GUI.
Interface complète

Tests réels

Optimi

=======================================================
ROADMAP V1 - 

NodeDrop — Roadmap du projet
1. Objet du document

Ce document définit la feuille de route du développement de NodeDrop.

Il décrit :

les phases de développement

les objectifs de chaque phase

les jalons techniques

les critères de validation

La roadmap permet de développer le logiciel progressivement, sans perdre la cohérence du projet.

2. Vision globale du projet

NodeDrop est développé en plusieurs étapes.

Étape 1

Créer une base logicielle stable.

Étape 2

Implémenter la découverte des machines.

Étape 3

Établir les connexions entre machines.

Étape 4

Implémenter le transfert de fichiers.

Étape 5

Stabiliser l’interface et les performances.

Étape 6

Préparer les évolutions futures.

3. Phase 0 — Initialisation du projet
Objectif

Préparer l’environnement de développement.

Tâches

créer l’arborescence du projet

créer les dossiers principaux

créer les fichiers de base

rédiger la documentation initiale

Résultat attendu

Le projet possède :

une structure claire

une documentation complète

une base prête pour le développement

4. Phase 1 — Base applicative
Objectif

Créer une application minimale qui démarre correctement.

Tâches

initialiser PySide6

créer la fenêtre principale

mettre en place le système de logs

créer le gestionnaire principal (AppManager)

Résultat attendu

L’application :

démarre

affiche une fenêtre

enregistre les logs

ne contient pas encore de réseau

5. Phase 2 — Découverte LAN
Objectif

Permettre aux machines NodeDrop de se détecter sur le réseau local.

Tâches

implémenter DiscoveryService

implémenter l’envoi d’annonces UDP

implémenter l’écoute UDP

connecter le système au PeerManager

afficher les machines détectées dans l’interface

Résultat attendu

Deux machines NodeDrop :

se détectent automatiquement

apparaissent dans la liste de l’interface.

6. Phase 3 — Connexions réseau
Objectif

Permettre l’établissement d’une connexion TCP entre deux machines.

Tâches

implémenter TcpListener

implémenter TcpClient

implémenter Session

envoyer les messages SESSION_REQUEST

gérer SESSION_ACCEPTED et SESSION_REJECTED

Résultat attendu

Une machine peut :

se connecter à une autre

recevoir une réponse.

7. Phase 4 — Authentification
Objectif

Ajouter la vérification du mot de passe.

Tâches

implémenter AuthManager

envoyer AUTH_REQUEST

envoyer AUTH_RESPONSE

vérifier le mot de passe

gérer AUTH_SUCCESS et AUTH_FAILED

Résultat attendu

Une connexion est possible uniquement si l’authentification réussit.

8. Phase 5 — Transfert de fichiers
Objectif

Permettre l’envoi réel de fichiers.

Tâches

implémenter TransferManager

implémenter l’envoi des métadonnées

implémenter l’envoi des blocs de données

implémenter la reconstruction des fichiers côté réception

implémenter la progression

Résultat attendu

Deux machines peuvent :

transférer un fichier

recevoir le fichier intact.

9. Phase 6 — Transfert avancé
Objectif

Améliorer le moteur de transfert.

Tâches

transfert de plusieurs fichiers

transfert de dossiers

amélioration de la progression

amélioration de la gestion d’erreurs

Résultat attendu

Le système supporte :

dossiers complets

transferts multiples.

10. Phase 7 — Interface utilisateur complète
Objectif

Finaliser l’expérience utilisateur.

Tâches

fenêtre de réception de transfert

fenêtre de progression

affichage du débit

affichage du temps restant

gestion des erreurs

Résultat attendu

L’interface devient intuitive et complète.

11. Phase 8 — Tests réels
Objectif

Tester NodeDrop sur plusieurs machines.

Tâches

tests sur réseau local

tests sur WiFi

tests sur Ethernet

tests avec fichiers volumineux

validation de la stabilité

Résultat attendu

Le logiciel fonctionne correctement sur plusieurs machines.

12. Phase 9 — Optimisation
Objectif

Améliorer les performances et la stabilité.

Tâches

optimiser les transferts

améliorer la gestion mémoire

améliorer la gestion des threads

améliorer les logs

13. Phase 10 — Packaging
Objectif

Distribuer NodeDrop comme application portable.

Tâches

création de l’exécutable avec PyInstaller

tests sur plusieurs machines

validation du lancement

Résultat attendu

NodeDrop peut être lancé sur un ordinateur sans installation.

14. Phase 11 — Stabilisation V1
Objectif

Finaliser la version 1.

Tâches

correction des bugs

amélioration UX

nettoyage du code

validation finale.

15. Version future (V2)

Fonctionnalités envisagées :

transfert distant

chiffrement avancé

comptes utilisateurs

historique des transferts

synchronisation de dossiers

amélioration des performances.

16. Jalons du projet
Jalons	Objectif
J1	application démarre
J2	découverte LAN
J3	connexion TCP
J4	authentification
J5	transfert simple
J6	transfert complet
J7	interface complète
J8	tests réseau
J9	optimisation
J10	release V1
17. Critères de réussite de la V1

La version 1 est validée si :

deux machines se détectent automatiquement

une connexion peut être établie

l’authentification fonctionne

un transfert fonctionne

les fichiers reçus sont corrects

l’interface est stable.

Prochaine étape

Maintenant que toute la documentation fondamentale existe, nous pouvons passer au développement réel.

La première étape du code sera :

src/utils/config.py
src/utils/log_utils.py
src/core/models.py

Ces trois fichiers constituent la base technique du projet.


=============================================================

