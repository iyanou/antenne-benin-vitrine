"""
Orchestrateur des scrapers ARCEP -- lance le sous-ensemble quotidien ou hebdomadaire,
un script a la fois, sans qu'une erreur sur l'un n'empeche les autres de tourner.

Usage : python orchestrate.py daily|weekly

daily  -> scrape_qos_national.py seul (page ARCEP hebdomadaire, verifiee tous les
          jours pour ne jamais rater une semaine des sa publication).
weekly -> les 9 autres scripts (donnees trimestrielles/annuelles/irregulieres,
          une execution hebdomadaire suffit largement).
"""
import subprocess
import sys
import time

HERE_SCRIPTS = {
    'daily': [
        'scrape_qos_national.py',
    ],
    'weekly': [
        'scrape_qos_regional.py',
        'scrape_market_reports.py',
        'scrape_sfm_reports.py',
        'scrape_complaints_reports.py',
        'scrape_postal_reports.py',
        'scrape_internet_reports.py',
        'scrape_fixe_reports.py',
        'scrape_tarifs_internet.py',
        'scrape_revenus_arcep.py',
    ],
}


def run_one(script):
    print(f"\n{'=' * 60}\n{script}\n{'=' * 60}")
    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        cwd=__import__('os').path.dirname(__import__('os').path.abspath(__file__)),
        capture_output=True, text=True,
    )
    elapsed = time.time() - start
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    ok = result.returncode == 0
    status = 'OK' if ok else 'ECHEC'
    print(f"-- {script} : {status} ({elapsed:.1f}s)")
    return script, ok, elapsed


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in HERE_SCRIPTS:
        print(f"Usage: {sys.argv[0]} daily|weekly", file=sys.stderr)
        sys.exit(2)

    mode = sys.argv[1]
    scripts = HERE_SCRIPTS[mode]
    print(f"Orchestration '{mode}' : {len(scripts)} script(s) a executer")

    results = [run_one(s) for s in scripts]

    print(f"\n{'=' * 60}\nResume ({mode})\n{'=' * 60}")
    n_ok = sum(1 for _, ok, _ in results if ok)
    for script, ok, elapsed in results:
        print(f"  {'OK   ' if ok else 'ECHEC'} {script} ({elapsed:.1f}s)")
    print(f"\n{n_ok}/{len(results)} script(s) reussi(s)")

    if n_ok < len(results):
        sys.exit(1)


if __name__ == '__main__':
    main()
