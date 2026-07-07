import unittest

from bot import build_role_pool, evaluate_game_state


class MafiaRoleBalanceTests(unittest.TestCase):
    def test_5_player_balance(self):
        self.assertEqual(
            build_role_pool(5),
            [
                "Don",
                "Commissioner",
                "Doctor",
                "Civilian",
                "Civilian",
            ],
        )

    def test_10_player_balance(self):
        self.assertEqual(
            build_role_pool(10),
            [
                "Don",
                "Mafioso",
                "Commissioner",
                "Doctor",
                "Guardian",
                "Elder",
                "Detective",
                "Civilian",
                "Civilian",
                "Civilian",
            ],
        )

    def test_15_player_balance(self):
        pool = build_role_pool(15)
        self.assertEqual(len(pool), 15)
        self.assertEqual(pool.count("Don") + pool.count("Mafioso"), 2)
        self.assertEqual(pool.count("Maniac"), 1)
        self.assertEqual(
            len(pool) - 2 - 1,
            12,
        )

    def test_out_of_range_players_raise_error(self):
        with self.assertRaises(ValueError):
            build_role_pool(4)

        with self.assertRaises(ValueError):
            build_role_pool(16)

    def test_civilians_win_when_mafia_is_eliminated(self):
        state = {
            "alive": {"A": False, "B": True, "C": True},
            "roles": {"A": "Don", "B": "Civilian", "C": "Civilian"},
        }
        result = evaluate_game_state(state)
        self.assertEqual(result["winner"], "civilians")

    def test_mafia_wins_when_majority_is_reached(self):
        state = {
            "alive": {"A": True, "B": True, "C": False},
            "roles": {"A": "Don", "B": "Mafioso", "C": "Doctor"},
        }
        result = evaluate_game_state(state)
        self.assertEqual(result["winner"], "mafia")


if __name__ == "__main__":
    unittest.main()
