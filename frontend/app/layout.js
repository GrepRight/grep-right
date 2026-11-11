import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "GrepRight",
  description: "Semantic code search",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">GrepRight</Link>
          <span className="tagline">semantic code search</span>
          <Link href="/search" className="navlink">Search</Link>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
