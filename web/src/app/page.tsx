import { redirect } from "next/navigation";

// The front door is the dashboard; its guard bounces anonymous
// visitors to /login and non-admin roles to their legacy home.
export default function HomePage() {
  redirect("/dashboard");
}
