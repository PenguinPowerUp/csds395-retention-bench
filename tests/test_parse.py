from retention_bench.datasets.wowah.parse import parse_text

SAMPLE = '''
Persistent_Storage = {
\t[1] = "0, 12/31/05 23:59:46, 1,0, , 5, Orc, Warrior, Durotar, no, 0",
\t[2] = "0, 01/01/06 00:00:02, 4,14,4, 35, Orc, Warrior, Orgrimmar, no, 0",
\t[3] = "garbage",
}
RoundInfo = {
\t[1] = "0, 1, 4, 135",
}
'''


def test_parses_records_and_stops_before_roundinfo():
    rows = parse_text(SAMPLE, "00-03-56")
    assert rows == [
        ("12/31/05 23:59:46", 0, -1, 5, "Orc", "Warrior", "Durotar", "00-03-56"),
        ("01/01/06 00:00:02", 14, 4, 35, "Orc", "Warrior", "Orgrimmar", "00-03-56"),
    ]
