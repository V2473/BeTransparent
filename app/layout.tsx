import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "«Яна»",
  description: "Генератор прототипів для Дії",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
