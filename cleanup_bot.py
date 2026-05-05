#!/usr/bin/env python3
"""
Clear webhook and reset bot updates queue
"""
import asyncio
from aiogram import Bot
from config import BOT_TOKEN

async def cleanup():
    bot = Bot(token=BOT_TOKEN)
    
    # Delete webhook (if active)
    try:
        await bot.delete_webhook()
        print("✅ Webhook deleted")
    except Exception as e:
        print(f"⚠️ Webhook delete: {e}")
    
    # Get pending updates (clears queue)
    try:
        updates = await bot.get_updates(limit=100)
        print(f"✅ Cleared {len(updates)} pending updates")
    except Exception as e:
        print(f"⚠️ Update clear: {e}")
    
    await bot.session.close()
    print("✅ Cleanup complete!")

if __name__ == "__main__":
    asyncio.run(cleanup())
