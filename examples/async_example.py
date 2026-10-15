"""Network-free async sample. For real requests use AsyncClient explicitly."""
import asyncio
from pydara.tse.samples import sample_async_client

async def main():
    async with sample_async_client() as client:
        quote = await client.get_quote("\u0641\u0648\u0644\u0627\u062f")
        print("SYNTHETIC, NOT LIVE:", quote.last_price)
        print(quote.to_frame())

if __name__ == "__main__":
    asyncio.run(main())
