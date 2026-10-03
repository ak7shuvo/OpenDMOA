import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="empty" style={{ marginTop: '2rem' }}>
      <span className="empty-title">Page not found</span>
      <span>This view does not exist in OpenDMO.</span>
      <Link className="btn primary sm" href="/">Back to overview</Link>
    </div>
  );
}
