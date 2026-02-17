"""
SQL script to create the required database tables.
This is for reference only - the Python code will create tables automatically.
"""

-- User processing status tracking
CREATE TABLE IF NOT EXISTS user_processing_status (
    user_id VARCHAR(255) PRIMARY KEY,
    last_teams_check TIMESTAMP,
    last_zoom_check TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_processing_status_active ON user_processing_status(is_active);
CREATE INDEX idx_user_processing_status_teams ON user_processing_status(last_teams_check);
CREATE INDEX idx_user_processing_status_zoom ON user_processing_status(last_zoom_check);

-- Meeting records
CREATE TABLE IF NOT EXISTS meeting_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    meeting_id VARCHAR(500) NOT NULL UNIQUE,
    platform VARCHAR(50) NOT NULL,
    meeting_title VARCHAR(500),
    meeting_start_time TIMESTAMP,
    meeting_end_time TIMESTAMP,
    recording_url TEXT,
    transcript_status VARCHAR(50) DEFAULT 'pending',
    summary_status VARCHAR(50) DEFAULT 'pending',
    summary_text TEXT,
    error_message TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_meeting_records_user ON meeting_records(user_id);
CREATE INDEX idx_meeting_records_meeting_id ON meeting_records(meeting_id);
CREATE INDEX idx_meeting_records_platform ON meeting_records(platform);

-- Processing logs
CREATE TABLE IF NOT EXISTS processing_logs (
    id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    users_processed INTEGER DEFAULT 0,
    meetings_found INTEGER DEFAULT 0,
    meetings_processed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    duration_seconds FLOAT,
    error_details TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_processing_logs_timestamp ON processing_logs(run_timestamp);
CREATE INDEX idx_processing_logs_status ON processing_logs(status);
