-- =====================================================================
-- GénoPed — Mesures de sécurisation de la base de données
-- À exécuter sur la base `genoped` avec un compte administrateur.
--   psql -h localhost -p 5433 -U postgres -d genoped -f sql/securisation.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. Table de traçabilité des consultations
--    (chaque analyse faite dans l'application y est enregistrée,
--     sans aucune donnée identifiante : pseudonymisation par conception)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consultations (
    id                      SERIAL PRIMARY KEY,
    horodatage              TIMESTAMP NOT NULL,
    age_patient             DOUBLE PRECISION,
    sexe                    VARCHAR(40),
    gene_maternel           VARCHAR(40),
    gene_paternel           VARCHAR(40),
    hypotonie_musculaire    INTEGER,
    retard_croissance       INTEGER,
    convulsions             INTEGER,
    detresse_respiratoire   INTEGER,
    regression_neurologique INTEGER,
    maladie_1               VARCHAR(80),
    probabilite_1           DOUBLE PRECISION,
    maladie_2               VARCHAR(80),
    probabilite_2           DOUBLE PRECISION,
    maladie_3               VARCHAR(80),
    probabilite_3           DOUBLE PRECISION,
    donnees_saisies         TEXT
);

-- ---------------------------------------------------------------------
-- 1. Principe du moindre privilège : l'application ne se connecte JAMAIS
--    avec le super-utilisateur `postgres`, mais avec un rôle dédié.
-- ---------------------------------------------------------------------
DROP ROLE IF EXISTS genoped_app;
CREATE ROLE genoped_app WITH LOGIN PASSWORD 'app_genoped_2026';

-- ---------------------------------------------------------------------
-- 2. Révocation des droits ouverts par défaut.
--    Par défaut PostgreSQL autorise tout le monde (PUBLIC) à créer des
--    objets dans le schéma public : on ferme cette porte.
-- ---------------------------------------------------------------------
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE genoped FROM PUBLIC;

-- ---------------------------------------------------------------------
-- 3. Droits strictement nécessaires accordés à l'application :
--    - lecture seule sur les dossiers historiques (`patients`)
--      -> l'application n'a aucune raison de modifier les données sources
--    - lecture + écriture sur la traçabilité (`consultations`)
-- ---------------------------------------------------------------------
GRANT CONNECT ON DATABASE genoped TO genoped_app;
GRANT USAGE ON SCHEMA public TO genoped_app;

GRANT SELECT ON TABLE patients TO genoped_app;
GRANT SELECT, INSERT ON TABLE consultations TO genoped_app;
GRANT USAGE, SELECT ON SEQUENCE consultations_id_seq TO genoped_app;

-- L'application ne peut ni supprimer ni modifier une consultation :
-- la traçabilité médicale est ainsi non altérable par le service applicatif.
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE consultations FROM genoped_app;

-- ---------------------------------------------------------------------
-- 4. Rôle de consultation (back-office / reporting) en lecture seule.
-- ---------------------------------------------------------------------
DROP ROLE IF EXISTS genoped_lecture;
CREATE ROLE genoped_lecture WITH LOGIN PASSWORD 'lecture_genoped_2026';
GRANT CONNECT ON DATABASE genoped TO genoped_lecture;
GRANT USAGE ON SCHEMA public TO genoped_lecture;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO genoped_lecture;

-- ---------------------------------------------------------------------
-- 5. Vérification : qui a quels droits ?
-- ---------------------------------------------------------------------
SELECT grantee AS role, table_name AS table, string_agg(privilege_type, ', ' ORDER BY privilege_type) AS droits
FROM information_schema.role_table_grants
WHERE grantee IN ('genoped_app', 'genoped_lecture')
GROUP BY grantee, table_name
ORDER BY grantee, table_name;
