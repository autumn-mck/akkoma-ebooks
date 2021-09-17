CREATE TABLE posts (
	post_id TEXT PRIMARY KEY NOT NULL,
	-- aka subject aka CW
	summary TEXT,
	content TEXT,
	-- UTC Unix timestamp in seconds
	published_at REAL NOT NULL
);

CREATE TABLE migrations (
	migration_version INTEGER NOT NULL
);
