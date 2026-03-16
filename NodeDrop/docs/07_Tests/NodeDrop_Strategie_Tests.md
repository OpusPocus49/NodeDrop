NodeDrop — Stratégie de tests
1. Objet du document

Ce document définit la stratégie de tests pour le projet NodeDrop.

Son objectif est de garantir que l’application fonctionne correctement dans les situations suivantes :

découverte des machines sur le réseau

connexion entre deux machines

authentification

transfert de fichiers

gestion des erreurs

transfert de fichiers volumineux

La stratégie de tests vise à détecter les problèmes le plus tôt possible pendant le développement.

2. Types de tests

Les tests du projet NodeDrop sont divisés en plusieurs catégories.

2.1 Tests unitaires

Les tests unitaires vérifient le comportement d’une fonction ou d’un module isolé.

Modules concernés :

file_utils

hash_utils

protocol

models

auth_manager

Objectif :

vérifier que chaque composant fonctionne correctement indépendamment des autres.

2.2 Tests d’intégration

Les tests d’intégration vérifient que plusieurs modules fonctionnent correctement ensemble.

Exemples :

découverte réseau + peer manager

connexion TCP + session

transfert manager + file_utils

Objectif :

vérifier que les composants interagissent correctement.

2.3 Tests réseau

Les tests réseau vérifient le fonctionnement du système sur plusieurs machines.

Scénarios testés :

détection automatique des machines

connexion entre deux machines

refus de connexion

authentification réussie

authentification échouée

Ces tests nécessitent au minimum deux ordinateurs sur le même réseau.

2.4 Tests de transfert

Ces tests vérifient le bon fonctionnement du moteur de transfert.

Scénarios :

transfert d’un fichier simple

transfert de plusieurs fichiers

transfert d’un dossier complet

transfert de fichiers volumineux

Objectifs :

vérifier l’intégrité des fichiers reçus

vérifier la progression du transfert

vérifier la stabilité du transfert

2.5 Tests de performance

Les tests de performance vérifient la capacité de NodeDrop à gérer des transferts importants.

Scénarios :

transfert de fichiers de plusieurs gigaoctets

transfert de centaines de fichiers

transfert sur réseau WiFi

transfert sur réseau Ethernet

Objectifs :

mesurer le débit

vérifier que l’application ne consomme pas trop de mémoire

vérifier que l’interface reste réactive.

2.6 Tests de robustesse

Ces tests vérifient le comportement de l’application en cas de problème.

Scénarios :

machine distante déconnectée

coupure réseau pendant un transfert

disque plein

erreur d’écriture fichier

mot de passe incorrect

Objectif :

vérifier que l’application gère correctement les erreurs.

3. Environnement de test

Les tests doivent être réalisés sur plusieurs configurations.

Configuration minimale

2 machines sur le même réseau local.

Exemple :

Machine A
Machine B

Configuration recommandée

3 machines :

Machine A
Machine B
Machine C

Cela permet de tester :

plusieurs connexions

plusieurs transferts

gestion des machines occupées.

4. Jeux de données de test

Pour tester correctement le système, plusieurs types de fichiers doivent être utilisés.

Petit fichier

1 MB

Fichier moyen

100 MB

Gros fichier

5 GB

Très gros fichier

20 GB

5. Vérification de l’intégrité

Après chaque transfert, il faut vérifier que les fichiers reçus sont identiques aux fichiers envoyés.

Méthodes possibles :

comparaison de taille

calcul de hash SHA256

Cette vérification est essentielle pour valider le moteur de transfert.

6. Tests de l’interface utilisateur

L’interface doit être testée pour vérifier :

affichage des machines détectées

affichage de la progression

affichage des erreurs

comportement des boutons

L’objectif est de garantir une expérience utilisateur claire et fiable.

7. Journalisation et diagnostic

Les logs doivent être utilisés pour analyser les problèmes.

Les tests doivent vérifier que les événements suivants sont enregistrés :

démarrage de l’application

découverte des machines

ouverture de session

transferts

erreurs.

8. Validation de la version V1

La version 1 de NodeDrop sera considérée comme stable si les conditions suivantes sont remplies :

deux machines se détectent automatiquement

une connexion peut être établie

l’authentification fonctionne

un transfert de fichiers fonctionne

les fichiers reçus sont intacts

l’interface reste stable

aucun crash n’est observé.

9. Évolution future des tests

Les versions futures pourront ajouter :

tests automatisés

tests de charge

tests multi-réseaux

tests de sécurité