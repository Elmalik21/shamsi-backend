"""
conduct_testing.py
==================
Automate user testing session management for Shamsi Smart beta programme.

Features:
- Generate unique test accounts with tracking IDs
- Log all API interactions per session
- Compute time-per-task and total session metrics
- Export anonymised per-session and aggregate reports
- Generate NPS and WTP summary statistics

Usage:
    # Create accounts for 10 beta participants
    python user_testing/conduct_testing.py create-accounts --count 10

    # Generate session summary after a session
    python user_testing/conduct_testing.py session-report --user USER001

    # Aggregate all sessions into testing report
    python user_testing/conduct_testing.py aggregate

    # Export anonymised data for analysis
    python user_testing/conduct_testing.py export --anonymise

Dependencies:
    pip install django reportlab matplotlib pandas
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import secrets
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent.resolve()
RESULTS_DIR = BASE_DIR / 'user_testing' / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TaskRecord:
    """One project task within a testing session."""
    task_id:      str          # A / B / C
    task_name:    str          # "Residential Villa" etc.
    started_at:   datetime
    completed_at: Optional[datetime] = None
    abandoned:    bool = False
    errors:       List[Dict]  = field(default_factory=list)
    notes:        str = ''

    @property
    def duration_minutes(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() / 60
        return None

    @property
    def completed(self) -> bool:
        return self.completed_at is not None and not self.abandoned


@dataclass
class ActionLog:
    """A single logged user action."""
    timestamp:  datetime
    action:     str
    endpoint:   str
    status:     int
    duration_ms: float
    metadata:   Dict = field(default_factory=dict)


@dataclass
class SurveyResponses:
    """Pre- and post-test survey answers."""
    # Pre-test
    current_tools:          List[str] = field(default_factory=list)
    baseline_time_hours:    float = 0.0
    pain_points:            str = ''
    projects_per_month:     int = 0
    pvsyst_usage_pct:       float = 0.0
    accuracy_confidence:    int = 0       # 1–10
    lost_client_due_to_speed: bool = False
    dream_features:         str = ''
    wtp_usd_per_month:      str = ''      # "Free" / "$10" / "$20" etc.
    feature_ranking:        List[str] = field(default_factory=list)

    # Post-test
    overall_rating:         int = 0       # 1–10
    comparison_vs_current:  str = ''      # "Much better" etc.
    time_saved_minutes:     float = 0.0
    accuracy_rating:        int = 0       # 1–10
    ai_confidence:          int = 0       # 1–10
    confusing_parts:        str = ''
    liked_most:             str = ''
    missing_features:       str = ''
    would_use_real:         str = ''      # "Yes" / "No" / "Only with verification"
    nps_score:             int = 0        # 0–10
    would_subscribe_pro:   str = ''       # "Definitely yes" etc.

    # Consent
    consent_written:        bool = False
    consent_video:          bool = False
    consent_company_name:   bool = False
    testimonial_text:       str = ''


@dataclass
class UserTestingSession:
    """Complete record of one participant's testing session."""
    user_id:     str
    company:     str
    tier:        str          # "Tier1" / "Tier2" / "Tier3"
    location:    str
    facilitator: str
    session_date: datetime = field(default_factory=datetime.now)

    tasks:   List[TaskRecord]  = field(default_factory=list)
    actions: List[ActionLog]   = field(default_factory=list)
    survey:  SurveyResponses   = field(default_factory=SurveyResponses)

    notes:           str = ''
    session_ended:   Optional[datetime] = None

    # ── Metric computation ────────────────────────────────────────────────

    def log_action(self, action: str, endpoint: str = '',
                   status: int = 200, duration_ms: float = 0,
                   metadata: Optional[Dict] = None) -> None:
        """Record a user API interaction."""
        self.actions.append(ActionLog(
            timestamp=datetime.now(),
            action=action,
            endpoint=endpoint,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata or {},
        ))

    def start_task(self, task_id: str, task_name: str) -> TaskRecord:
        task = TaskRecord(task_id=task_id, task_name=task_name, started_at=datetime.now())
        self.tasks.append(task)
        return task

    def complete_task(self, task_id: str, notes: str = '') -> None:
        for t in self.tasks:
            if t.task_id == task_id and t.completed_at is None:
                t.completed_at = datetime.now()
                t.notes = notes
                return
        raise ValueError(f"Task {task_id!r} not found or already completed")

    def abandon_task(self, task_id: str, reason: str = '') -> None:
        for t in self.tasks:
            if t.task_id == task_id:
                t.abandoned = True
                t.notes = reason
                return

    def log_error(self, task_id: str, error_type: str,
                  description: str, severity: str = 'Minor') -> None:
        """Record a usability error during a task."""
        for t in self.tasks:
            if t.task_id == task_id:
                t.errors.append({
                    'type': error_type,
                    'description': description,
                    'severity': severity,          # Critical / Major / Minor / Cosmetic
                    'timestamp': datetime.now().isoformat(),
                })
                return

    def calculate_metrics(self) -> Dict:
        """Compute all session KPIs."""
        completed_tasks   = [t for t in self.tasks if t.completed]
        task_times        = [t.duration_minutes for t in completed_tasks if t.duration_minutes]
        all_errors        = [e for t in self.tasks for e in t.errors]
        critical_errors   = [e for e in all_errors if e['severity'] == 'Critical']

        total_session_min = None
        if self.session_ended:
            total_session_min = (self.session_ended - self.session_date).total_seconds() / 60

        api_calls   = len(self.actions)
        avg_latency = (sum(a.duration_ms for a in self.actions) / api_calls
                       if api_calls else 0)

        return {
            'user_id'              : self.user_id,
            'company'              : self.company,
            'tier'                 : self.tier,
            'session_date'         : self.session_date.date().isoformat(),
            'tasks_completed'      : len(completed_tasks),
            'tasks_total'          : len(self.tasks),
            'completion_rate_pct'  : len(completed_tasks) / max(len(self.tasks), 1) * 100,
            'mean_task_time_min'   : round(sum(task_times) / len(task_times), 1) if task_times else None,
            'total_session_min'    : round(total_session_min, 1) if total_session_min else None,
            'errors_total'         : len(all_errors),
            'errors_critical'      : len(critical_errors),
            'api_calls'            : api_calls,
            'avg_api_latency_ms'   : round(avg_latency, 1),
            # Survey KPIs
            'baseline_time_hours'  : self.survey.baseline_time_hours,
            'time_saved_min'       : self.survey.time_saved_minutes,
            'overall_rating'       : self.survey.overall_rating,
            'accuracy_rating'      : self.survey.accuracy_rating,
            'nps_score'            : self.survey.nps_score,
            'would_subscribe_pro'  : self.survey.would_subscribe_pro,
            'wtp_usd'              : self.survey.wtp_usd_per_month,
            'liked_most'           : self.survey.liked_most,
            'missing_features'     : self.survey.missing_features,
        }

    def export_json(self, output_path: Optional[Path] = None) -> Path:
        """Serialise session to JSON for analysis."""
        data = {
            'user_id'     : self.user_id,
            'company'     : self.company,
            'tier'        : self.tier,
            'location'    : self.location,
            'session_date': self.session_date.isoformat(),
            'metrics'     : self.calculate_metrics(),
            'tasks'       : [asdict(t) for t in self.tasks],
            'survey'      : asdict(self.survey),
            'notes'       : self.notes,
        }
        # Anonymise company name in exported data
        data['company_anon'] = f"Company_{self.tier}_{self.user_id[-3:]}"

        out = output_path or (RESULTS_DIR / f'session_{self.user_id}.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Account generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_test_accounts(count: int = 10) -> List[Dict]:
    """
    Generate unique test accounts.
    Returns list of account dicts (save to CSV or create via Django admin).
    """
    accounts = []
    for i in range(1, count + 1):
        user_id  = f"BETA{i:03d}"
        password = secrets.token_urlsafe(12)
        token    = secrets.token_hex(24)
        accounts.append({
            'user_id'        : user_id,
            'email'          : f"{user_id.lower()}@shamsi-test.invalid",
            'password'       : password,
            'api_token'      : token,
            'tier'           : 'Tier1' if i <= 3 else ('Tier2' if i <= 7 else 'Tier3'),
            'created_at'     : datetime.now().isoformat(),
            'optimizations'  : 999,   # Unlimited during testing
            'exports_enabled': True,
            'cv_enabled'     : True,
        })

    out = RESULTS_DIR / 'test_accounts.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(accounts[0].keys()))
        writer.writeheader()
        writer.writerows(accounts)

    print(f"Generated {count} test accounts → {out}")
    print("\nIMPORTANT: Keep test_accounts.csv confidential — contains passwords!")
    return accounts


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate analysis
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_sessions(results_dir: Path = RESULTS_DIR) -> Dict:
    """Load all session JSON files and compute aggregate statistics."""
    session_files = list(results_dir.glob('session_BETA*.json'))
    if not session_files:
        print(f"[WARN] No session files found in {results_dir}")
        return {}

    sessions = []
    for f in session_files:
        with open(f) as fh:
            sessions.append(json.load(fh))

    metrics = [s['metrics'] for s in sessions]
    n = len(metrics)

    def mean(key: str) -> Optional[float]:
        vals = [m[key] for m in metrics if m.get(key) is not None and isinstance(m[key], (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    def count_value(key: str, value) -> int:
        return sum(1 for m in metrics if m.get(key) == value)

    def pct_yes_or_positive(key: str) -> float:
        positive = {'Definitely yes', 'Probably yes', 'Yes'}
        vals = [m.get(key, '') for m in metrics]
        return round(sum(1 for v in vals if v in positive) / n * 100, 1) if n else 0

    # NPS calculation
    nps_scores = [m['nps_score'] for m in metrics if isinstance(m.get('nps_score'), int)]
    promoters  = sum(1 for s in nps_scores if s >= 9)
    detractors = sum(1 for s in nps_scores if s <= 6)
    nps        = round((promoters - detractors) / len(nps_scores) * 100) if nps_scores else None

    # WTP distribution
    wtp_vals = [m.get('wtp_usd', '') for m in metrics]
    wtp_dist = {}
    for v in wtp_vals:
        wtp_dist[v] = wtp_dist.get(v, 0) + 1

    aggregate = {
        'n_sessions'             : n,
        'completion_rate_pct'    : mean('completion_rate_pct'),
        'mean_task_time_min'     : mean('mean_task_time_min'),
        'mean_time_saved_min'    : mean('time_saved_min'),
        'mean_overall_rating'    : mean('overall_rating'),
        'mean_accuracy_rating'   : mean('accuracy_rating'),
        'mean_nps'               : mean('nps_score'),
        'nps_net'                : nps,
        'critical_errors_total'  : sum(m.get('errors_critical', 0) for m in metrics),
        'pct_would_subscribe'    : pct_yes_or_positive('would_subscribe_pro'),
        'wtp_distribution'       : wtp_dist,
        # Success criteria
        'PASS_rating'            : (mean('overall_rating') or 0) >= 7.0,
        'PASS_time_saved'        : (mean('time_saved_min') or 0) >= 60.0,
        'PASS_zero_critical_bugs': sum(m.get('errors_critical', 0) for m in metrics) == 0,
        'PASS_wtp_60pct'         : pct_yes_or_positive('would_subscribe_pro') >= 60.0,
    }
    aggregate['GO_NOGO'] = all([
        aggregate['PASS_rating'],
        aggregate['PASS_time_saved'],
        aggregate['PASS_zero_critical_bugs'],
        aggregate['PASS_wtp_60pct'],
    ])

    return aggregate


def print_aggregate_report(agg: Dict) -> None:
    """Print a formatted aggregate testing report."""
    print("\n" + "═" * 60)
    print("  Shamsi Smart — Beta Testing Aggregate Report")
    print("═" * 60)
    print(f"  Sessions analysed      : {agg.get('n_sessions', 0)}")
    print(f"  Task completion rate   : {agg.get('completion_rate_pct', '?')}%")
    print(f"  Mean task time         : {agg.get('mean_task_time_min', '?')} min")
    print(f"  Mean time saved        : {agg.get('mean_time_saved_min', '?')} min")
    print()
    print("  User Satisfaction")
    print(f"    Overall rating       : {agg.get('mean_overall_rating', '?')}/10  "
          f"{'✅' if agg.get('PASS_rating') else '❌'} (target ≥7)")
    print(f"    Accuracy rating      : {agg.get('mean_accuracy_rating', '?')}/10")
    print(f"    NPS score            : {agg.get('mean_nps', '?')}/10  "
          f"(Net: {agg.get('nps_net', '?')})")
    print()
    print("  Business Validation")
    print(f"    Would subscribe Pro  : {agg.get('pct_would_subscribe', '?')}%  "
          f"{'✅' if agg.get('PASS_wtp_60pct') else '❌'} (target ≥60%)")
    print(f"    WTP distribution     : {agg.get('wtp_distribution', {})}")
    print()
    print("  Quality")
    print(f"    Critical bugs        : {agg.get('critical_errors_total', '?')}  "
          f"{'✅' if agg.get('PASS_zero_critical_bugs') else '❌'} (target 0)")
    print()
    verdict = "✅ GO — Launch public beta" if agg.get('GO_NOGO') else "❌ NO-GO — Address issues first"
    print(f"  LAUNCH VERDICT: {verdict}")
    print("═" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Shamsi Smart — User Testing Manager')
    sub = p.add_subparsers(dest='command')

    # create-accounts
    ca = sub.add_parser('create-accounts', help='Generate test account credentials')
    ca.add_argument('--count', type=int, default=10)

    # session-report
    sr = sub.add_parser('session-report', help='Print metrics for one session')
    sr.add_argument('--user', required=True, help='User ID e.g. BETA001')

    # aggregate
    sub.add_parser('aggregate', help='Aggregate all sessions into a report')

    # export
    ex = sub.add_parser('export', help='Export session data')
    ex.add_argument('--anonymise', action='store_true')

    return p.parse_args()


def main():
    args = parse_args()

    if args.command == 'create-accounts':
        generate_test_accounts(args.count)

    elif args.command == 'session-report':
        session_file = RESULTS_DIR / f'session_{args.user}.json'
        if not session_file.exists():
            print(f"[ERROR] Session file not found: {session_file}")
            sys.exit(1)
        with open(session_file) as f:
            data = json.load(f)
        print(json.dumps(data['metrics'], indent=2))

    elif args.command == 'aggregate':
        agg = aggregate_sessions()
        if agg:
            print_aggregate_report(agg)
            out = RESULTS_DIR / 'aggregate_report.json'
            with open(out, 'w') as f:
                json.dump(agg, f, indent=2)
            print(f"\nSaved to: {out}")
        else:
            print("No sessions found. Run some sessions first.")

    elif args.command == 'export':
        files = list(RESULTS_DIR.glob('session_*.json'))
        all_data = []
        for fp in files:
            with open(fp) as f:
                data = json.load(f)
            if args.anonymise:
                data.pop('company', None)
                data.pop('location', None)
                data['user_id'] = data.get('company_anon', data['user_id'])
            all_data.append(data)
        out = RESULTS_DIR / 'all_sessions_export.json'
        with open(out, 'w') as f:
            json.dump(all_data, f, indent=2, default=str)
        print(f"Exported {len(all_data)} sessions → {out}")

    else:
        print("Shamsi Smart User Testing Manager")
        print("Commands: create-accounts, session-report, aggregate, export")
        print("Run with --help for details")


if __name__ == '__main__':
    main()
