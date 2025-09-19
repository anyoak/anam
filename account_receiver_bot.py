import asyncio
import logging
import csv
import io
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Document
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, select
from typing import List
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS", "[]"))
MINIMUM_WITHDRAW = float(os.getenv("MINIMUM_WITHDRAW", 3.0))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = "sqlite+aiosqlite:///bot.db"
engine = create_async_engine(DATABASE_URL, echo=True)
Base = declarative_base()

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True)
    balance = Column(Float, default=0.0)
    country_code = Column(String)
    two_step_password = Column(String, nullable=True)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    account_type = Column(String)  # session, json, string
    country_code = Column(String)
    status = Column(String, default="pending")  # pending, verified, active, frozen, banned, logged_out
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    lost_at = Column(DateTime, nullable=True)
    session_data = Column(String, nullable=True)  # Placeholder for session data

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    amount = Column(Float)
    usdt_address = Column(String)
    status = Column(String, default="pending")  # pending, success, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    tx_hash = Column(String, nullable=True)

class CountryConfig(Base):
    __tablename__ = "country_configs"
    id = Column(Integer, primary_key=True)
    country_code = Column(String, unique=True)
    price = Column(Float)
    capacity = Column(Integer)
    confirmation_time = Column(Integer)  # in minutes

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Bot setup
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Keyboards
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Account"))
    markup.add(KeyboardButton("Capacity"))
    markup.add(KeyboardButton("Withdraw"))
    markup.add(KeyboardButton("History"))
    return markup

def get_admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Set Minimum Withdraw"))
    markup.add(KeyboardButton("Add Country Code"))
    markup.add(KeyboardButton("Update Prices"))
    markup.add(KeyboardButton("View All Balances"))
    markup.add(KeyboardButton("Manage Numbers"))
    markup.add(KeyboardButton("Delete All Balances"))
    markup.add(KeyboardButton("Export Data"))
    markup.add(KeyboardButton("View Statistics"))
    markup.add(KeyboardButton("Set 2-Step Password"))
    markup.add(KeyboardButton("Update Capacity"))
    markup.add(KeyboardButton("Update Confirmation Time"))
    markup.add(KeyboardButton("Delete Country Code"))
    markup.add(KeyboardButton("View Balance by User"))
    return markup

# User Commands
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    async with AsyncSession(engine) as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(telegram_id=str(user_id))
            session.add(user)
            await session.commit()
    
    if user_id in ADMIN_IDS:
        await message.answer("Welcome Admin!", reply_markup=get_admin_menu())
    else:
        await message.answer("Welcome to Account Receiver Bot!", reply_markup=get_main_menu())

@dp.message(Command("cancel"))
async def cancel_command(message: types.Message):
    await message.answer("Current process cancelled.")

@dp.message(lambda message: message.text == "Account")
async def account_command(message: types.Message):
    user_id = message.from_user.id
    async with AsyncSession(engine) as session:
        user = await session.get(User, user_id)
        stmt = select(Account).where(Account.user_id == user_id)
        accounts = (await session.execute(stmt)).scalars().all()
        verified = len([a for a in accounts if a.status == "verified"])
        pending = len([a for a in accounts if a.status == "pending"])
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        balance = user.balance if user else 0.0
        response = (
            f"User ID: {user_id}\n"
            f"Balance: ${balance:.2f}\n"
            f"Verified Accounts: {verified}\n"
            f"Pending Accounts: {pending}\n"
            f"Current Time: {current_time}"
        )
        await message.answer(response)

@dp.message(lambda message: message.text == "Capacity")
async def capacity_command(message: types.Message):
    async with AsyncSession(engine) as session:
        stmt = select(CountryConfig)
        configs = (await session.execute(stmt)).scalars().all()
        response = "\n".join([f"{c.country_code}: {c.capacity} numbers" for c in configs])
        await message.answer(f"Available Capacity:\n{response or 'No countries configured'}")

@dp.message(lambda message: message.text == "Withdraw")
async def withdraw_command(message: types.Message):
    await message.answer("Please provide USDT-BEP20 address (e.g., /withdraw 0x...)")

@dp.message(Command("withdraw"))
async def withdraw_process_command(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Please provide a USDT-BEP20 address")
        return
    usdt_address = args[1]
    async with AsyncSession(engine) as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("User not found")
            return
        if user.balance < MINIMUM_WITHDRAW:
            await message.answer(f"Minimum withdrawal is ${MINIMUM_WITHDRAW:.2f}")
            return
        withdrawal = Withdrawal(
            user_id=user.id,
            amount=user.balance,
            usdt_address=usdt_address
        )
        session.add(withdrawal)
        user.balance = 0
        await session.commit()
        await message.answer("Withdrawal request submitted for manual processing!")

@dp.message(lambda message: message.text == "History")
async def history_command(message: types.Message):
    async with AsyncSession(engine) as session:
        stmt = select(Withdrawal).where(Withdrawal.user_id == message.from_user.id)
        withdrawals = (await session.execute(stmt)).scalars().all()
        response = "\n".join([
            f"ID: {w.id}, Amount: ${w.amount:.2f}, Address: {w.usdt_address}, "
            f"Status: {w.status}, Date: {w.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            for w in withdrawals
        ])
        await message.answer(f"Withdrawal History:\n{response or 'No transactions'}")

# Admin Commands
@dp.message(lambda message: message.text == "Set Minimum Withdraw" and message.from_user.id in ADMIN_IDS)
async def set_minimum_withdraw(message: types.Message):
    await message.answer("Enter new minimum withdraw amount (e.g., /setminwithdraw 5)")

@dp.message(Command("setminwithdraw"))
async def set_min_withdraw_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Please provide an amount")
        return
    try:
        global MINIMUM_WITHDRAW
        MINIMUM_WITHDRAW = float(args[1])
        # Update .env or database for persistence
        await message.answer(f"Minimum withdraw set to ${MINIMUM_WITHDRAW:.2f}")
    except ValueError:
        await message.answer("Invalid amount")

@dp.message(lambda message: message.text == "Set 2-Step Password" and message.from_user.id in ADMIN_IDS)
async def set_two_step(message: types.Message):
    await message.answer("Enter user ID and password (e.g., /set2step 123456789 password123)")

@dp.message(Command("set2step"))
async def set_two_step_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Provide user ID and password")
        return
    try:
        user_id = int(args[1])
        password = args[2]
        async with AsyncSession(engine) as session:
            user = await session.get(User, user_id)
            if user:
                user.two_step_password = password
                await session.commit()
                await message.answer(f"2-step password set for user {user_id}")
            else:
                await message.answer("User not found")
    except ValueError:
        await message.answer("Invalid user ID")

@dp.message(lambda message: message.text == "Add Country Code" and message.from_user.id in ADMIN_IDS)
async def add_country_code(message: types.Message):
    await message.answer("Enter country code, price, capacity, confirmation time (e.g., /addcountry IN 0.5 100 60)")

@dp.message(Command("addcountry"))
async def add_country_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 5:
        await message.answer("Provide country code, price, capacity, confirmation time")
        return
    try:
        async with AsyncSession(engine) as session:
            config = CountryConfig(
                country_code=args[1].upper(),
                price=float(args[2]),
                capacity=int(args[3]),
                confirmation_time=int(args[4])
            )
            session.add(config)
            await session.commit()
            await message.answer(f"Country {args[1].upper()} added!")
    except ValueError:
        await message.answer("Invalid input")

@dp.message(lambda message: message.text == "Update Prices" and message.from_user.id in ADMIN_IDS)
async def update_prices(message: types.Message):
    await message.answer("Enter country code and new price (e.g., /updateprice US 0.7)")

@dp.message(Command("updateprice"))
async def update_price_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Provide country code and price")
        return
    try:
        async with AsyncSession(engine) as session:
            stmt = select(CountryConfig).where(CountryConfig.country_code == args[1].upper())
            config = (await session.execute(stmt)).scalar()
            if config:
                config.price = float(args[2])
                await session.commit()
                await message.answer(f"Price for {args[1].upper()} updated!")
            else:
                await message.answer("Country not found")
    except ValueError:
        await message.answer("Invalid price")

@dp.message(lambda message: message.text == "Update Capacity" and message.from_user.id in ADMIN_IDS)
async def update_capacity(message: types.Message):
    await message.answer("Enter country code and new capacity (e.g., /updatecapacity US 200)")

@dp.message(Command("updatecapacity"))
async def update_capacity_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Provide country code and capacity")
        return
    try:
        async with AsyncSession(engine) as session:
            stmt = select(CountryConfig).where(CountryConfig.country_code == args[1].upper())
            config = (await session.execute(stmt)).scalar()
            if config:
                config.capacity = int(args[2])
                await session.commit()
                await message.answer(f"Capacity for {args[1].upper()} updated!")
            else:
                await message.answer("Country not found")
    except ValueError:
        await message.answer("Invalid capacity")

@dp.message(lambda message: message.text == "Update Confirmation Time" and message.from_user.id in ADMIN_IDS)
async def update_confirmation_time(message: types.Message):
    await message.answer("Enter country code and new time in minutes (e.g., /updateconfirmation US 30)")

@dp.message(Command("updateconfirmation"))
async def update_confirmation_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Provide country code and time")
        return
    try:
        async with AsyncSession(engine) as session:
            stmt = select(CountryConfig).where(CountryConfig.country_code == args[1].upper())
            config = (await session.execute(stmt)).scalar()
            if config:
                config.confirmation_time = int(args[2])
                await session.commit()
                await message.answer(f"Confirmation time for {args[1].upper()} updated!")
            else:
                await message.answer("Country not found")
    except ValueError:
        await message.answer("Invalid time")

@dp.message(lambda message: message.text == "Delete Country Code" and message.from_user.id in ADMIN_IDS)
async def delete_country_code(message: types.Message):
    await message.answer("Enter country code to delete (e.g., /deletecountry US)")

@dp.message(Command("deletecountry"))
async def delete_country_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide country code")
        return
    async with AsyncSession(engine) as session:
        stmt = select(CountryConfig).where(CountryConfig.country_code == args[1].upper())
        config = (await session.execute(stmt)).scalar()
        if config:
            await session.delete(config)
            await session.commit()
            await message.answer(f"Country {args[1].upper()} deleted!")
        else:
            await message.answer("Country not found")

@dp.message(lambda message: message.text == "View Balance by User" and message.from_user.id in ADMIN_IDS)
async def view_balance_by_user(message: types.Message):
    await message.answer("Enter user ID (e.g., /viewbalance 123456789)")

@dp.message(Command("viewbalance"))
async def view_balance_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide user ID")
        return
    try:
        user_id = int(args[1])
        async with AsyncSession(engine) as session:
            user = await session.get(User, user_id)
            if user:
                await message.answer(f"User {user_id} balance: ${user.balance:.2f}")
            else:
                await message.answer("User not found")
    except ValueError:
        await message.answer("Invalid user ID")

@dp.message(lambda message: message.text == "View All Balances" and message.from_user.id in ADMIN_IDS)
async def view_all_balances(message: types.Message):
    async with AsyncSession(engine) as session:
        stmt = select(User)
        users = (await session.execute(stmt)).scalars().all()
        response = "\n".join([f"User {u.telegram_id}: ${u.balance:.2f}" for u in users])
        await message.answer(f"All Balances:\n{response or 'No users'}")

@dp.message(lambda message: message.text == "Delete All Balances" and message.from_user.id in ADMIN_IDS)
async def delete_all_balances(message: types.Message):
    async with AsyncSession(engine) as session:
        await session.execute("UPDATE users SET balance = 0")
        await session.commit()
        await message.answer("All user balances reset to $0")

@dp.message(lambda message: message.text == "Manage Numbers" and message.from_user.id in ADMIN_IDS)
async def manage_numbers(message: types.Message):
    await message.answer(
        "Options:\n"
        "/viewpending - View all pending numbers\n"
        "/viewpendingbyuser <user_id> - View pending by user\n"
        "/deletepending - Delete all pending numbers\n"
        "/deletependingbycountry <code> - Delete pending by country\n"
        "/deletependingbyuser <user_id> - Delete pending by user"
    )

@dp.message(Command("viewpending"))
async def view_pending(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with AsyncSession(engine) as session:
        stmt = select(Account).where(Account.status == 'pending')
        accounts = (await session.execute(stmt)).scalars().all()
        response = "\n".join([f"ID: {a.id}, User: {a.user_id}, Country: {a.country_code}" for a in accounts])
        await message.answer(f"Pending Numbers:\n{response or 'None'}")

@dp.message(Command("viewpendingbyuser"))
async def view_pending_by_user(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide user ID")
        return
    try:
        user_id = int(args[1])
        async with AsyncSession(engine) as session:
            stmt = select(Account).where(Account.status == 'pending', Account.user_id == user_id)
            accounts = (await session.execute(stmt)).scalars().all()
            response = "\n".join([f"ID: {a.id}, Country: {a.country_code}" for a in accounts])
            await message.answer(f"Pending Numbers for User {user_id}:\n{response or 'None'}")
    except ValueError:
        await message.answer("Invalid user ID")

@dp.message(Command("deletepending"))
async def delete_pending(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with AsyncSession(engine) as session:
        await session.execute("DELETE FROM accounts WHERE status = 'pending'")
        await session.commit()
        await message.answer("All pending numbers deleted!")

@dp.message(Command("deletependingbycountry"))
async def delete_pending_by_country(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide country code")
        return
    country_code = args[1].upper()
    async with AsyncSession(engine) as session:
        await session.execute("DELETE FROM accounts WHERE status = 'pending' AND country_code = :code", {"code": country_code})
        await session.commit()
        await message.answer(f"Pending numbers for {country_code} deleted!")

@dp.message(Command("deletependingbyuser"))
async def delete_pending_by_user(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide user ID")
        return
    try:
        user_id = int(args[1])
        async with AsyncSession(engine) as session:
            await session.execute("DELETE FROM accounts WHERE status = 'pending' AND user_id = :uid", {"uid": user_id})
            await session.commit()
            await message.answer(f"Pending numbers for user {user_id} deleted!")
    except ValueError:
        await message.answer("Invalid user ID")

@dp.message(lambda message: message.text == "Export Data" and message.from_user.id in ADMIN_IDS)
async def export_data(message: types.Message):
    await message.answer(
        "Export Options:\n"
        "/export_tdata <country|all> - Export tdata by country or all\n"
        "/export_sessions <country|all> - Export session files by country or all\n"
        "/export_json <country|all> - Export json by country or all\n"
        "/export_frozen - Export frozen accounts\n"
        "/export_active <user_id|all> - Export active accounts by user or all"
    )

async def export_accounts(session: AsyncSession, filter_stmt):
    accounts = (await session.execute(filter_stmt)).scalars().all()
    if not accounts:
        return None
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "User ID", "Type", "Country", "Status", "Session Data"])
    for a in accounts:
        writer.writerow([a.id, a.user_id, a.account_type, a.country_code, a.status, a.session_data])
    output.seek(0)
    return output

@dp.message(Command("export_tdata"))
async def export_tdata(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide country code or 'all'")
        return
    param = args[1].lower()
    async with AsyncSession(engine) as session:
        if param == 'all':
            stmt = select(Account).where(Account.account_type == 'session')  # Assuming tdata is session
        else:
            stmt = select(Account).where(Account.account_type == 'session', Account.country_code == param.upper())
        output = await export_accounts(session, stmt)
        if output:
            await message.answer_document(types.InputFile(io.BytesIO(output.getvalue().encode()), filename="tdata_export.csv"))
        else:
            await message.answer("No data to export")

@dp.message(Command("export_sessions"))
async def export_sessions(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide country code or 'all'")
        return
    param = args[1].lower()
    async with AsyncSession(engine) as session:
        if param == 'all':
            stmt = select(Account).where(Account.account_type == 'session')
        else:
            stmt = select(Account).where(Account.account_type == 'session', Account.country_code == param.upper())
        output = await export_accounts(session, stmt)
        if output:
            await message.answer_document(types.InputFile(io.BytesIO(output.getvalue().encode()), filename="sessions_export.csv"))
        else:
            await message.answer("No data to export")

@dp.message(Command("export_json"))
async def export_json(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide country code or 'all'")
        return
    param = args[1].lower()
    async with AsyncSession(engine) as session:
        if param == 'all':
            stmt = select(Account).where(Account.account_type == 'json')
        else:
            stmt = select(Account).where(Account.account_type == 'json', Account.country_code == param.upper())
        output = await export_accounts(session, stmt)
        if output:
            await message.answer_document(types.InputFile(io.BytesIO(output.getvalue().encode()), filename="json_export.csv"))
        else:
            await message.answer("No data to export")

@dp.message(Command("export_frozen"))
async def export_frozen(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with AsyncSession(engine) as session:
        stmt = select(Account).where(Account.status == 'frozen')
        output = await export_accounts(session, stmt)
        if output:
            await message.answer_document(types.InputFile(io.BytesIO(output.getvalue().encode()), filename="frozen_export.csv"))
        else:
            await message.answer("No frozen accounts")

@dp.message(Command("export_active"))
async def export_active(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide user ID or 'all'")
        return
    param = args[1].lower()
    async with AsyncSession(engine) as session:
        if param == 'all':
            stmt = select(Account).where(Account.status == 'active')
        else:
            try:
                user_id = int(param)
                stmt = select(Account).where(Account.status == 'active', Account.user_id == user_id)
            except ValueError:
                await message.answer("Invalid user ID")
                return
        output = await export_accounts(session, stmt)
        if output:
            await message.answer_document(types.InputFile(io.BytesIO(output.getvalue().encode()), filename="active_export.csv"))
        else:
            await message.answer("No active accounts")

@dp.message(lambda message: message.text == "View Statistics" and message.from_user.id in ADMIN_IDS)
async def view_statistics(message: types.Message):
    async with AsyncSession(engine) as session:
        total_users = await session.scalar(select(func.count(User.id.distinct())))
        total_accounts = await session.scalar(select(func.count(Account.id)))
        accounts_by_status = await session.execute(select(Account.status, func.count(Account.id)).group_by(Account.status))
        accounts_by_status = dict(accounts_by_status.all())
        accounts_by_country = await session.execute(select(Account.country_code, func.count(Account.id)).group_by(Account.country_code))
        accounts_by_country = dict(accounts_by_country.all())
        response = f"Total Users: {total_users}\nTotal Accounts: {total_accounts}\n"
        response += "Accounts by Status:\n" + "\n".join([f"{status}: {count}" for status, count in accounts_by_status.items()]) + "\n"
        response += "Accounts by Country:\n" + "\n".join([f"{country}: {count}" for country, count in accounts_by_country.items()])
        await message.answer(response)

# Account Creation
@dp.message(Command("createaccount"))
async def create_account_command(message: types.Message):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Usage: /createaccount <type> <country_code> (e.g., /createaccount session US)")
        return
    account_type = args[1].lower()
    if account_type not in ["session", "json", "string"]:
        await message.answer("Invalid type: session, json, string")
        return
    country_code = args[2].upper()
    async with AsyncSession(engine) as session:
        stmt = select(CountryConfig).where(CountryConfig.country_code == country_code)
        config = (await session.execute(stmt)).scalar()
        if not config or config.capacity <= 0:
            await message.answer("No capacity for this country")
            return
        account = Account(
            user_id=message.from_user.id,
            account_type=account_type,
            country_code=country_code,
            session_data="dummy_session_data"  # Placeholder
        )
        session.add(account)
        config.capacity -= 1
        await session.commit()
        await message.answer(f"{account_type.capitalize()} account for {country_code} created!")

# Report Ban/Logout
@dp.message(Command("reportban"))
async def report_ban(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide account ID")
        return
    try:
        account_id = int(args[1])
        async with AsyncSession(engine) as session:
            account = await session.get(Account, account_id)
            if not account or account.user_id != message.from_user.id:
                await message.answer("Account not found or not yours")
                return
            stmt = select(CountryConfig).where(CountryConfig.country_code == account.country_code)
            config = (await session.execute(stmt)).scalar()
            time_since_creation = (datetime.utcnow() - account.created_at).total_seconds() / 60
            account.status = "banned"
            account.lost_at = datetime.utcnow()
            if time_since_creation <= config.confirmation_time:
                # No balance added
                await message.answer("Account banned within confirmation time. No balance adjustment.")
            else:
                # Log to admin
                for admin_id in ADMIN_IDS:
                    await bot.send_message(admin_id, f"Account {account_id} lost after confirmation: User {account.user_id}, Country {account.country_code}")
            await session.commit()
    except ValueError:
        await message.answer("Invalid account ID")

# Verify Account (Admin)
@dp.message(Command("verifyaccount"))
async def verify_account(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Provide account ID")
        return
    try:
        account_id = int(args[1])
        async with AsyncSession(engine) as session:
            account = await session.get(Account, account_id)
            if not account:
                await message.answer("Account not found")
                return
            if account.status != "pending":
                await message.answer("Account not pending")
                return
            user = await session.get(User, account.user_id)
            stmt = select(CountryConfig).where(CountryConfig.country_code == account.country_code)
            config = (await session.execute(stmt)).scalar()
            user.balance += config.price
            account.status = "verified"
            account.verified_at = datetime.utcnow()
            await session.commit()
            await message.answer(f"Account {account_id} verified. Balance added to user {account.user_id}")
    except ValueError:
        await message.answer("Invalid account ID")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())