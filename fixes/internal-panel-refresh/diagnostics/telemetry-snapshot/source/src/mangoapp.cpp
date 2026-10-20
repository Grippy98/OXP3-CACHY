/* Verbatim Gamescope 3.16.25 patched output-update fixture; MIT.
 * See ../../../../gamescope/accepted-runtime/LICENSE. */
void mangoapp_output_update( uint64_t vblanktime, uint64_t ulBasePlaneCommitID, uint32_t uBasePlaneAppID )
{
	static uint64_t s_uLastBasePlaneCommitID = 0;
	if ( s_uLastBasePlaneCommitID != ulBasePlaneCommitID )
	{
		static uint64_t s_uLastBasePlaneUpdateVBlankTime = vblanktime;
        uint64_t last_frametime = s_uLastBasePlaneUpdateVBlankTime;
        uint64_t frametime = vblanktime - last_frametime;
		s_uLastBasePlaneUpdateVBlankTime = vblanktime;
		s_uLastBasePlaneCommitID = ulBasePlaneCommitID;
        if ( last_frametime > vblanktime )
            return;

		mangoapp_update( frametime, uint64_t(~0ull), uint64_t(~0ull) );

        if ( cv_mangoapp_use_output_timing )
        {
            wlserver_lock();
            wlserver_app_presented( uBasePlaneAppID, frametime );
            wlserver_unlock();
        }
	}
}

// The Vulkan present-wait path has no per-present base snapshot yet.
void mangoapp_output_update( uint64_t vblanktime )
{
	mangoapp_output_update( vblanktime, g_uCurrentBasePlaneCommitID, g_uCurrentBasePlaneAppID );
}
