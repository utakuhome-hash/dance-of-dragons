
-- Dance of Dragons Database
-- Initial database schema

CREATE TABLE houses (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    sigil TEXT,
    castle VARCHAR(150),
    treasury BIGINT NOT NULL DEFAULT 0,
    food BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE players (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    telegram_id BIGINT UNIQUE,
    role VARCHAR(30) NOT NULL DEFAULT 'player',
    house_id BIGINT REFERENCES houses(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (role IN ('admin', 'player', 'house_leader', 'treasurer'))
);

CREATE TABLE game_clock (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    game_year INTEGER NOT NULL DEFAULT 129,
    season VARCHAR(20) NOT NULL DEFAULT 'spring',
    last_year_update TIMESTAMPTZ,
    last_season_update TIMESTAMPTZ,

    CHECK (season IN ('spring', 'summer', 'autumn', 'winter'))
);

INSERT INTO game_clock (id, game_year, season)
VALUES (1, 129, 'spring')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_id BIGINT REFERENCES players(id),
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50),
    target_id BIGINT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_players_house ON players(house_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_id);

