import random
from collections import Counter
from typing import Any, Dict, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import TOKEN


ROLE_SCHEMES = {
    5: ["Don", "Commissioner", "Doctor", "Civilian", "Civilian"],
    6: ["Don", "Commissioner", "Doctor", "Elder", "Civilian", "Civilian"],
    7: ["Don", "Mafioso", "Commissioner", "Doctor", "Elder", "Civilian", "Civilian"],
    8: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Civilian", "Civilian", "Civilian"],
    9: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Civilian", "Civilian", "Civilian"],
    10: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Civilian", "Civilian"],
    11: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Civilian", "Civilian", "Maniac"],
    12: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Civilian", "Civilian", "Maniac", "Immortal"],
    13: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Civilian", "Civilian", "Maniac", "Immortal", "Journalist"],
    14: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Civilian", "Civilian", "Maniac", "Immortal", "Journalist", "Hunter"],
    15: ["Don", "Mafioso", "Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Civilian", "Civilian", "Maniac", "Immortal", "Journalist", "Hunter", "Priest"],
}


MAFIA_ROLES = {"Don", "Mafioso"}
CIVILIAN_ROLES = {"Commissioner", "Doctor", "Guardian", "Elder", "Detective", "Civilian", "Immortal", "Journalist", "Hunter", "Priest"}
INDEPENDENT_ROLES = {"Maniac"}


def build_role_pool(player_count: int) -> List[str]:
    if not 5 <= player_count <= 15:
        raise ValueError("Кількість гравців має бути від 5 до 15")
    return list(ROLE_SCHEMES[player_count])


def build_game_state(player_count: int) -> Dict[str, Any]:
    roles = build_role_pool(player_count)
    return {
        "player_count": player_count,
        "roles": roles,
        "alive": {i: True for i in range(player_count)},
        "phase": "lobby",
    }


def make_session() -> Dict[str, Any]:
    return {
        "players": [],
        "started": False,
        "roles": {},
        "alive": {},
        "phase": "lobby",
        "votes": {},
        "night_votes": {},
        "last_result": "",
        "menu_message_id": None,
    }


def assign_roles(player_names: List[str]) -> Dict[str, str]:
    if len(player_names) < 5 or len(player_names) > 15:
        raise ValueError("Кількість гравців має бути від 5 до 15")

    roles = build_role_pool(len(player_names))
    shuffled_players = list(player_names)
    random.shuffle(shuffled_players)
    shuffled_roles = list(roles)
    random.shuffle(shuffled_roles)
    return {player: role for player, role in zip(shuffled_players, shuffled_roles)}


def evaluate_game_state(state: Dict[str, Any]) -> Dict[str, Any]:
    alive_players = [name for name, alive in state.get("alive", {}).items() if alive]
    if not alive_players:
        return {"winner": "draw", "reason": "all dead"}

    alive_roles = {name: state["roles"].get(name) for name in alive_players if name in state["roles"]}
    mafia_alive = sum(1 for role in alive_roles.values() if role in MAFIA_ROLES)
    civilian_alive = sum(1 for role in alive_roles.values() if role in CIVILIAN_ROLES)
    independent_alive = sum(1 for role in alive_roles.values() if role in INDEPENDENT_ROLES)

    if mafia_alive == 0 and independent_alive == 0:
        return {"winner": "civilians", "reason": "mafia eliminated"}

    if mafia_alive > 0 and mafia_alive >= (len(alive_players) - mafia_alive):
        return {"winner": "mafia", "reason": "mafia has majority"}

    if independent_alive > 0 and mafia_alive == 0 and civilian_alive == 0:
        return {"winner": "independent", "reason": "maniac survives"}

    return {"winner": None, "reason": "ongoing"}


SESSIONS: Dict[int, Dict[str, Any]] = {}


if TOKEN:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (
            "Привіт! Це повноцінний бот для гри в мафію в групі.\n"
            "Натисни кнопку нижче, щоб створити або приєднатися до гри."
        )
        await update.message.reply_text(text, reply_markup=build_main_menu())

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "Подробиці про гру:\n"
            "- У грі 5–15 гравців.\n"
            "- Існує мафія, мирні та незалежний Маніяк.\n"
            "- На 15 гравців максимум 2 мафії і 1 Маніяк.\n"
            "- Ніч: мафія обирає жертву, а потім починається день.\n"
            "- День: усі гравці голосують кнопками за підозрюваного.\n"
            "- Перемога мафії: коли вона має більшість або знищує всіх мирних.\n"
            "- Перемога мирних: коли знищена мафія.\n"
            "\nРолі:\n"
            "- Дон мафії — лідер мафії. Він знає, хто його союзники, і керує ночними діями мафії.\n"
            "- Мафіозі — звичайні члени мафії. Вночі вони діють разом із Донoм, намагаючись прибрати мирних.\n"
            "- Маніяк — незалежний гравець, що грає проти всіх. Він не союзник ні мафії, ні мирних, і прагне залишитися єдиним вижившим.\n"
            "- Комісар — перевіряє одного гравця вночі, щоб дізнатися, чи він мафія.\n"
            "- Лікар — може захистити одного гравця від вбивства вночі.\n"
            "- Охоронець — охороняє одного гравця вночі, зменшуючи ризик убивства.\n"
            "- Староста — допомагає мирним, даючи їм додаткову інформацію про гру.\n"
            "- Детектив — розслідує підозрюваних і може отримати важливі підказки.\n"
            "- Журналіст — отримує інформацію про події в грі і допомагає мирним приймати рішення.\n"
            "- Безсмертний — дуже важка роль: його складно вбити, і він може довго виживати.\n"
            "- Мисливець — може помститися під час останнього ходу, якщо його вб'ють.\n"
            "- Священник — має особливу роль, яка допомагає захищати або впливати на хід гри.\n"
            "- Мирний житель — звичайний мирний гравець. Його мета — виявити мафію й вижити до кінця.\n"
            "\nКнопки:\n"
            "- Новa гра — створює сесію.\n"
            "- Приєднатися — додає гравця.\n"
            "- Почати — роздає ролі.\n"
            "- Статус — показує стан.\n"
            "- Наступний раунд — змінює ніч/день.\n"
            "- Голосування — відкриває меню голосування."
        )
        await update.message.reply_text(help_text, reply_markup=build_main_menu())

    async def roles_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        roles_text = (
            "📖 Детальний опис ролей:\n\n"
            "👑 Дон мафії — керівник мафії. Він знає союзників і керує нічними діями.\n"
            "🕵️ Мафіозі — звичайні члени мафії. Вночі діють разом із Доном.\n"
            "🧠 Маніяк — незалежний гравець, який грає проти всіх.\n"
            "🔍 Комісар — перевіряє одного гравця вночі.\n"
            "🩺 Лікар — захищає одного гравця від вбивства.\n"
            "🛡 Охоронець — охороняє одного гравця вночі.\n"
            "👨‍⚖️ Староста — допомагає мирним і дає важливу інформацію.\n"
            "🕵 Детектив — розслідує підозрюваних.\n"
            "📰 Журналіст — отримує інформацію про гру.\n"
            "💪 Безсмертний — важко вбити.\n"
            "🎯 Мисливець — може помститися, якщо його вб'ють.\n"
            "⛪ Священник — має особливу роль у грі.\n"
            "🏘 Мирний житель — звичайний мирний гравець."
        )
        await update.message.reply_text(roles_text, reply_markup=build_main_menu())

    def build_main_menu(session: Dict[str, Any] | None = None) -> InlineKeyboardMarkup:
        if not session or not session.get("started"):
            buttons = [
                [InlineKeyboardButton("🆕 Нова гра", callback_data="new_game")],
                [InlineKeyboardButton("🧑‍🤝‍🧑 Приєднатися", callback_data="join_game")],
                [InlineKeyboardButton("🧩 Ролі", callback_data="roles")],
                [InlineKeyboardButton("❓ Правила", callback_data="help")],
            ]
        else:
            buttons = [
                [InlineKeyboardButton("📊 Статус", callback_data="status_game")],
                [InlineKeyboardButton("🌙 Наступний раунд", callback_data="night_action")],
                [InlineKeyboardButton("🗳 Голосування", callback_data="vote_menu")],
                [InlineKeyboardButton("🧩 Ролі", callback_data="roles")],
                [InlineKeyboardButton("❓ Правила", callback_data="help")],
                [InlineKeyboardButton("⏹ Завершити гру", callback_data="end_game")],
            ]
        return InlineKeyboardMarkup(buttons)

    async def send_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE, session: Dict[str, Any], text: str) -> None:
        if session.get("menu_message_id"):
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=session["menu_message_id"],
                    text=text,
                    reply_markup=build_main_menu(session),
                )
            except Exception:
                pass
        else:
            message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_main_menu(session))
            session["menu_message_id"] = message.message_id

    async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        session = make_session()
        SESSIONS[chat_id] = session
        await update.message.reply_text(
            "Нова сесія створена. Натисни кнопку «Приєднатися», щоб долучитися."
            " Коли збереться 5+ гравців — натисни «Почати».",
            reply_markup=build_main_menu(session),
        )

    async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        user = update.effective_user
        session = SESSIONS.setdefault(chat_id, make_session())
        if session["started"]:
            await update.message.reply_text("Гра вже розпочалась, нових учасників не приймають.")
            return

        player_name = user.first_name or user.username or "Гравець"
        if any(entry["id"] == user.id for entry in session["players"]):
            await update.message.reply_text("Ви вже в цій грі.")
            return

        session["players"].append({"id": user.id, "name": player_name})
        names = ", ".join(item["name"] for item in session["players"])
        await update.message.reply_text(f"{player_name} приєднався до гри.\nГравці: {names}", reply_markup=build_main_menu(session))

    async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        session = SESSIONS.get(chat_id)
        if not session:
            await update.message.reply_text("Спочатку створіть гру через кнопку «Нова гра».")
            return

        players = session["players"]
        if len(players) < 5:
            await update.message.reply_text("Для старту потрібно щонайменше 5 гравців.")
            return

        role_map = assign_roles([item["name"] for item in players])
        session["roles"] = role_map
        session["alive"] = {name: True for name in role_map}
        session["started"] = True
        session["phase"] = "night"
        session["votes"] = {}
        session["night_votes"] = {}
        session["last_result"] = "Гра розпочалась. Ніч."

        await update.message.reply_text(
            f"Гра розпочалась на {len(players)} гравців.\nПочинається ніч."
            " Натисни «Наступний раунд», щоб перейти до дня або продовжити гру.",
            reply_markup=build_main_menu(session),
        )

        for player in players:
            role = role_map[player["name"]]
            await context.bot.send_message(
                chat_id=player["id"],
                text=f"Ваша роль: {role}\nГра розпочалася. У боті є кнопки для управління фазами."
            )

    async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        session = SESSIONS.get(chat_id)
        if not session:
            await update.message.reply_text("Поки немає активної гри.")
            return

        players = ", ".join(item["name"] for item in session["players"])
        alive = ", ".join(name for name, is_alive in session.get("alive", {}).items() if is_alive)
        text = (
            f"Фаза: {session['phase']}\n"
            f"Гравці: {players or 'ніхто'}\n"
            f"Живі: {alive or 'ніхто'}\n"
            f"Результат: {session.get('last_result', '')}"
        )
        await update.message.reply_text(text, reply_markup=build_main_menu(session))

    async def resolve_night(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        session = SESSIONS.get(chat_id)
        if not session or not session["started"]:
            await update.message.reply_text("Немає активної гри.")
            return

        if session["phase"] != "night":
            session["phase"] = "night"
            session["votes"] = {}
            session["last_result"] = "Почалася нова ніч."
            await update.message.reply_text("Почалася нова ніч. Натисни «Наступний раунд», щоб завершити її.", reply_markup=build_main_menu(session))
            return

        alive_names = [name for name, is_alive in session["alive"].items() if is_alive]
        target = random.choice(alive_names)
        session["night_votes"] = {"target": target}
        session["phase"] = "day"
        session["last_result"] = f"Ніч завершилась. Обрано жертву: {target}."
        await update.message.reply_text(
            f"🌙 Ніч завершилась. Жертва: {target}.\nТепер день — голосуйте кнопками.",
            reply_markup=build_main_menu(session),
        )

    async def show_vote_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        session = SESSIONS.get(chat_id)
        if not session or not session["started"]:
            await update.message.reply_text("Немає активної гри.")
            return

        if session["phase"] != "day":
            await update.message.reply_text("Зараз не день, тому голосування недоступне.")
            return

        alive_names = [name for name, is_alive in session["alive"].items() if is_alive]
        buttons = [[InlineKeyboardButton(name, callback_data=f"vote:{name}")] for name in alive_names]
        buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="status_game")])
        await update.message.reply_text("Оберіть, за кого голосуєте:", reply_markup=InlineKeyboardMarkup(buttons))

    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()
        chat_id = update.effective_chat.id
        session = SESSIONS.get(chat_id)
        data = query.data or ""

        if data == "new_game":
            session = make_session()
            SESSIONS[chat_id] = session
            await query.edit_message_text(
                "Нова сесія створена. Натисни «Приєднатися», щоб долучитися.",
                reply_markup=build_main_menu(session),
            )
            return

        if data == "join_game":
            if not session:
                session = make_session()
                SESSIONS[chat_id] = session
            if session["started"]:
                await query.edit_message_text("Гра вже розпочалась, нових учасників не приймають.", reply_markup=build_main_menu(session))
                return
            user = update.effective_user
            player_name = user.first_name or user.username or "Гравець"
            if any(entry["id"] == user.id for entry in session["players"]):
                await query.edit_message_text("Ви вже в цій грі.", reply_markup=build_main_menu(session))
                return
            session["players"].append({"id": user.id, "name": player_name})
            names = ", ".join(item["name"] for item in session["players"])
            await query.edit_message_text(f"{player_name} приєднався до гри.\nГравці: {names}", reply_markup=build_main_menu(session))
            return

        if data == "start_game":
            if not session:
                await query.edit_message_text("Сесія ще не створена.", reply_markup=build_main_menu())
                return
            if len(session["players"]) < 5:
                await query.edit_message_text("Для старту потрібно щонайменше 5 гравців.", reply_markup=build_main_menu(session))
                return
            role_map = assign_roles([item["name"] for item in session["players"]])
            session["roles"] = role_map
            session["alive"] = {name: True for name in role_map}
            session["started"] = True
            session["phase"] = "night"
            session["votes"] = {}
            session["night_votes"] = {}
            session["last_result"] = "Гра розпочалась. Ніч."
            await query.edit_message_text("Гра розпочалась. Нічний раунд.", reply_markup=build_main_menu(session))
            for player in session["players"]:
                await context.bot.send_message(chat_id=player["id"], text=f"Ваша роль: {role_map[player['name']]}\nГра розпочалась.")
            return

        if data == "status_game":
            if not session:
                await query.edit_message_text("Поки немає активної гри.", reply_markup=build_main_menu())
                return
            players = ", ".join(item["name"] for item in session["players"])
            alive = ", ".join(name for name, is_alive in session.get("alive", {}).items() if is_alive)
            text = f"Фаза: {session['phase']}\nГравці: {players or 'ніхто'}\nЖиві: {alive or 'ніхто'}\nРезультат: {session.get('last_result', '')}"
            await query.edit_message_text(text, reply_markup=build_main_menu(session))
            return

        if data == "roles":
            roles_text = (
                "📖 Детальний опис ролей:\n\n"
                "👑 Дон мафії — керівник мафії. Він знає союзників і керує нічними діями.\n"
                "🕵️ Мафіозі — звичайні члени мафії. Вночі діють разом із Доном.\n"
                "🧠 Маніяк — незалежний гравець, який грає проти всіх.\n"
                "🔍 Комісар — перевіряє одного гравця вночі.\n"
                "🩺 Лікар — захищає одного гравця від вбивства.\n"
                "🛡 Охоронець — охороняє одного гравця вночі.\n"
                "👨‍⚖️ Староста — допомагає мирним і дає важливу інформацію.\n"
                "🕵 Детектив — розслідує підозрюваних.\n"
                "📰 Журналіст — отримує інформацію про гру.\n"
                "💪 Безсмертний — важко вбити.\n"
                "🎯 Мисливець — може помститися, якщо його вб'ють.\n"
                "⛪ Священник — має особливу роль у грі.\n"
                "🏘 Мирний житель — звичайний мирний гравець."
            )
            await query.edit_message_text(roles_text, reply_markup=build_main_menu(session))
            return

        if data == "help":
            help_text = (
                "Подробиці про гру:\n"
                "- У грі 5–15 гравців.\n"
                "- Існує мафія, мирні та незалежний Маніяк.\n"
                "- На 15 гравців максимум 2 мафії і 1 Маніяк.\n"
                "- Ніч: мафія обирає жертву, а потім починається день.\n"
                "- День: усі гравці голосують кнопками.\n"
                "- Перемога мафії: коли вона має більшість або знищує всіх мирних.\n"
                "- Перемога мирних: коли знищена мафія.\n"
                "\nРолі:\n"
                "- Дон мафії — лідер мафії.\n"
                "- Мафіозі — члени мафії.\n"
                "- Маніяк — незалежна роль против всіх.\n"
                "- Комісар — перевіряє.\n"
                "- Лікар — захищає.\n"
                "- Охоронець — охороняє.\n"
                "- Староста — допомагає мирним.\n"
                "- Детектив — шукає підозрюваних.\n"
                "- Журналіст — отримує інформацію.\n"
                "- Безсмертний — не може бути вбитий.\n"
                "- Мисливець — помщається.\n"
                "- Священник — особлива роль.\n"
                "- Мирний житель — звичайний мирний."
            )
            await query.edit_message_text(help_text, reply_markup=build_main_menu(session))
            return

        if data == "night_action":
            if not session or not session["started"]:
                await query.edit_message_text("Немає активної гри.", reply_markup=build_main_menu())
                return
            if session["phase"] != "night":
                session["phase"] = "night"
                session["votes"] = {}
                session["last_result"] = "Почалася нова ніч."
                await query.edit_message_text("Почалася нова ніч.", reply_markup=build_main_menu(session))
                return
            alive_names = [name for name, is_alive in session["alive"].items() if is_alive]
            target = random.choice(alive_names)
            session["night_votes"] = {"target": target}
            session["phase"] = "day"
            session["last_result"] = f"Ніч завершилась. Обрано жертву: {target}."
            await query.edit_message_text(f"🌙 Ніч завершилась. Жертва: {target}.\nТепер день — голосуйте кнопками.", reply_markup=build_main_menu(session))
            return

        if data == "vote_menu":
            if not session or not session["started"]:
                await query.edit_message_text("Немає активної гри.", reply_markup=build_main_menu())
                return
            if session["phase"] != "day":
                await query.edit_message_text("Зараз не день, голосування недоступне.", reply_markup=build_main_menu(session))
                return
            alive_names = [name for name, is_alive in session["alive"].items() if is_alive]
            buttons = [[InlineKeyboardButton(name, callback_data=f"vote:{name}")] for name in alive_names]
            buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="status_game")])
            await query.edit_message_text("Оберіть гравця для голосування:", reply_markup=InlineKeyboardMarkup(buttons))
            return

        if data == "end_game":
            if session:
                session.clear()
            SESSIONS[chat_id] = make_session()
            await query.edit_message_text("Гру завершено.", reply_markup=build_main_menu())
            return

        if data.startswith("vote:"):
            if not session or not session["started"]:
                await query.edit_message_text("Немає активної гри.", reply_markup=build_main_menu())
                return
            target = data.split(":", 1)[1]
            if target not in session["alive"] or not session["alive"][target]:
                await query.edit_message_text("Цей гравець уже мертвий.", reply_markup=build_main_menu(session))
                return
            voter_name = update.effective_user.first_name or update.effective_user.username or "Гравець"
            session["votes"][voter_name] = target
            threshold = max(3, (sum(1 for alive in session["alive"].values() if alive) // 2) + 1)
            if len(session["votes"]) >= threshold:
                vote_counter = Counter(session["votes"].values())
                eliminated = vote_counter.most_common(1)[0][0]
                session["alive"][eliminated] = False
                session["phase"] = "night"
                session["votes"] = {}
                session["last_result"] = f"Вибрано на голосуванні: {eliminated}."
                result = evaluate_game_state(session)
                if result["winner"]:
                    session["phase"] = "finished"
                    await query.edit_message_text(f"Гра закінчена! Перемогла сторона: {result['winner']}.", reply_markup=build_main_menu(session))
                else:
                    await query.edit_message_text(f"{eliminated} був(ла) вибраний(а) на голосуванні.", reply_markup=build_main_menu(session))
            else:
                await query.edit_message_text(f"Ваш голос за {target} зафіксовано.\nПотрібно ще {threshold - len(session['votes'])} голосів для виведення.", reply_markup=build_main_menu(session))
            return

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message.text and update.message.text.startswith("/"):
            return

    def build_application() -> Any:
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("roles", roles_info))
        application.add_handler(CommandHandler("newgame", new_game))
        application.add_handler(CommandHandler("join", join_game))
        application.add_handler(CommandHandler("startgame", start_game))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("night", resolve_night))
        application.add_handler(CommandHandler("day", resolve_night))
        application.add_handler(CommandHandler("vote", show_vote_menu))
        application.add_handler(CommandHandler("end", end_game))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        return application


async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = SESSIONS.get(chat_id)
    if session:
        session.clear()
    SESSIONS[chat_id] = make_session()
    await update.message.reply_text("Гру завершено.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = SESSIONS.get(chat_id)
    if not session:
        await update.message.reply_text("Поки немає активної гри.")
        return
    players = ", ".join(item["name"] for item in session["players"])
    alive = ", ".join(name for name, is_alive in session.get("alive", {}).items() if is_alive)
    await update.message.reply_text(
        f"Фаза: {session['phase']}\n"
        f"Гравці: {players or 'ніхто'}\n"
        f"Живі: {alive or 'ніхто'}\n"
        f"Результат: {session.get('last_result', '')}",
        reply_markup=build_main_menu(session),
    )


if __name__ == "__main__":
    if not TOKEN:
        print("TG_BOT_TOKEN is not set; bot will not start.")
    else:
        build_application().run_polling()
