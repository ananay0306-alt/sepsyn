"""--feed-q end to end. Heuristic steps 16 and 17 from the command line."""
from sepsyn.cli import main


def test_design_reports_the_feed_condition_without_being_asked(capsys):
    """Step 17 is not opt-in. Every design prints its q."""
    assert main(["--feed", "Benzene:60,Toluene:40", "--T", "298.15",
                 "--design", "--light-key", "Benzene",
                 "--heavy-key", "Toluene"]) == 0
    out = capsys.readouterr().out
    assert "q = " in out
    assert "as it arrives" in out


def test_feed_q_flag_imposes_the_condition_and_says_so(capsys):
    assert main(["--feed", "Benzene:60,Toluene:40", "--T", "298.15",
                 "--design", "--light-key", "Benzene",
                 "--heavy-key", "Toluene", "--feed-q", "1.0"]) == 0
    out = capsys.readouterr().out
    assert "q = 1.000" in out
    assert "imposed" in out
