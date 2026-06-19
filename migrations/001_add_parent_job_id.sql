ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS parent_job_id UUID NULL;

CREATE INDEX IF NOT EXISTS ix_jobs_parent_job_id
    ON jobs (parent_job_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_jobs_parent_job_id'
    ) THEN
        ALTER TABLE jobs
            ADD CONSTRAINT fk_jobs_parent_job_id
            FOREIGN KEY (parent_job_id)
            REFERENCES jobs(id)
            ON DELETE SET NULL;
    END IF;
END
$$;
