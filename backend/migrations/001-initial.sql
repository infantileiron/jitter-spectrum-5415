-- Initial demo schema comes from versioned SQLAlchemy metadata.
-- DOUBLE time/frequency parameters; JSON retains original points, no imputation.
-- Unique dataset/window/study names and report.run_id. Production requires reviewed ALTER migrations.
CREATE INDEX IF NOT EXISTS ix_spectral_runs_status ON spectral_runs(status);

-- Multi-link cross-check (added later, same metadata-create-all workflow):
-- comparison_studies.window_ids is a JSON array of sampling_windows.id (2..12, distinct links,
-- one shared dataset). comparison_runs persist the joint Lomb-Scargle result and phase
-- differences separately from single-link spectral_runs; legacy single-link results are untouched.
CREATE INDEX IF NOT EXISTS ix_comparison_runs_status ON comparison_runs(status);
CREATE INDEX IF NOT EXISTS ix_comparison_runs_study_id ON comparison_runs(study_id);
