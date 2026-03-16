# NodeDrop — Cahier des charges V1

## 1. Présentation
Nom du logiciel

NodeDrop

Version concernée

Version 1 (V1)

Description générale

NodeDrop est une application portable permettant de transférer facilement des fichiers et dossiers entre plusieurs ordinateurs connectés à un même réseau local.

L’application détecte automatiquement les machines exécutant NodeDrop sur le réseau et permet d’établir une connexion entre deux ordinateurs afin d’échanger des fichiers.

Chaque connexion doit être validée par l’utilisateur distant et authentifiée par un mot de passe.

L’application vise à simplifier les transferts de fichiers volumineux sans nécessiter de configuration réseau complexe.

## 2. Objectifs de la version 1

La première version de NodeDrop doit permettre :

la découverte automatique des ordinateurs sur un réseau local

la connexion entre deux machines

la validation des demandes de connexion

l’envoi et la réception de fichiers et dossiers

l’affichage d’une progression de transfert

la gestion des transferts volumineux

la journalisation des opérations

La version 1 est limitée au réseau local (LAN).

## 3. Périmètre de la version 1
Inclus dans la V1

découverte automatique des machines NodeDrop

liste des machines disponibles

demande de connexion

acceptation ou refus d’une connexion

authentification par mot de passe

transfert de fichiers

transfert de dossiers

transfert de multiples fichiers

barre de progression

affichage du débit

estimation du temps restant

journal des événements

Exclus de la V1

Les fonctionnalités suivantes ne seront pas développées dans la première version :

transfert entre réseaux différents

serveur central

comptes utilisateurs

synchronisation automatique

chiffrement avancé

reprise automatique après coupure

application mobile

Ces fonctionnalités pourront être intégrées dans des versions futures.

## 4. Environnement technique
Systèmes supportés

Version 1 :

Windows

Versions futures possibles :

Linux

macOS

Réseau

Type de réseau :

réseau local (LAN)

Connexion :

réseau domestique

réseau d’entreprise

réseau WiFi ou Ethernet

## 5. Fonctionnalités détaillées
5.1 Découverte des machines

L’application doit détecter automatiquement les autres machines exécutant NodeDrop sur le réseau local.

Chaque instance NodeDrop doit :

annoncer sa présence sur le réseau

écouter les annonces des autres machines

Les machines détectées doivent apparaître dans l’interface.

Informations affichées :

nom de la machine

adresse IP locale

statut (disponible / occupé / hors ligne)

5.2 Demande de connexion

Un utilisateur doit pouvoir :

sélectionner une machine distante

envoyer une demande de connexion

La machine distante doit recevoir une notification indiquant :

l’ordinateur demandeur

la demande de connexion

L’utilisateur distant peut :

accepter

refuser

5.3 Authentification

La connexion entre deux machines doit nécessiter la saisie d’un mot de passe.

Objectifs :

empêcher une connexion non autorisée

limiter l’accès aux machines autorisées

Le mot de passe doit être vérifié avant autorisation du transfert.

5.4 Sélection des fichiers

L’utilisateur doit pouvoir sélectionner :

un fichier

plusieurs fichiers

un dossier complet

L’application doit calculer :

le nombre de fichiers

la taille totale à transférer

5.5 Transfert de fichiers

Le transfert doit être réalisé de manière progressive.

Caractéristiques :

transfert par blocs de données

gestion des fichiers volumineux

utilisation de mémoire limitée

Le transfert doit fonctionner pour :

fichiers simples

ensembles de fichiers

dossiers complets

5.6 Progression du transfert

Pendant un transfert, l’interface doit afficher :

barre de progression globale

nom du fichier en cours

taille transférée

débit de transfert

estimation du temps restant

5.7 Réception de fichiers

Lorsqu’un transfert est initié :

Une fenêtre doit apparaître sur la machine distante.

Elle doit afficher :

nom de l’ordinateur source

nombre de fichiers

taille totale

options :

accepter

refuser

L’utilisateur doit pouvoir choisir le dossier de destination.

5.8 Journalisation

L’application doit conserver un journal des événements.

Événements enregistrés :

démarrage de l’application

détection des machines

connexions

transferts

erreurs éventuelles

Les journaux doivent être enregistrés dans un dossier dédié.

## 6. Performance

L’application doit être capable de transférer des fichiers volumineux.

Objectif :

transfert de fichiers pouvant atteindre plusieurs dizaines de gigaoctets

Le système doit éviter :

surcharge mémoire

blocage de l’interface utilisateur

## 7. Interface utilisateur

L’interface doit être simple et claire.

Elle doit comporter :

Fenêtre principale

Contenant :

liste des machines détectées

boutons de connexion

bouton d’envoi de fichiers

zone d’information

Fenêtre de transfert

Affichant :

progression du transfert

informations sur le débit

temps restant

Fenêtre de réception

Permettant :

accepter

refuser

choisir un dossier de destination

## 8. Architecture logicielle (vue générale)

L’application sera organisée en modules.

Modules principaux :

Interface graphique

Gestion de l’affichage et des interactions utilisateur.

Découverte réseau

Gestion de la détection des machines sur le réseau local.

Gestion des connexions

Établissement des sessions entre machines.

Moteur de transfert

Gestion de l’envoi et de la réception des fichiers.

Gestion des fichiers

Manipulation des dossiers et des chemins de fichiers.

Journalisation

Gestion des logs.

## 9. Évolutions prévues

Les versions futures pourront inclure :

transfert distant entre réseaux

serveur de signalisation

chiffrement avancé

comptes utilisateurs

synchronisation de dossiers

historique avancé des transferts

## 10. Critères de réussite de la V1

La version 1 sera considérée comme fonctionnelle lorsque :

deux machines NodeDrop se détectent automatiquement

une connexion peut être établie

un transfert de fichiers fonctionne correctement

les fichiers reçus sont intacts

l’interface affiche correctement la progression

les journaux sont enregistrés